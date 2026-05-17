from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import os

from database import get_db
from models import Recording, RecordingStatus
from livekit.api import LiveKitAPI, AccessToken, VideoGrants
import asyncio
import json

router = APIRouter(prefix="/recording", tags=["Recording"])

LIVEKIT_URL = os.getenv("LIVEKIT_PUBLIC_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")


class RecordingResponse(BaseModel):
    id: str
    room_name: str
    triggered_by: str
    started_at: datetime
    stopped_at: Optional[datetime]
    status: str
    file_paths: Optional[str]

    class Config:
        from_attributes = True


async def _send_livekit_data(room: str, payload: dict):
    """Broadcast a data message to all participants in a LiveKit room via REST API."""
    try:
        import httpx
        from livekit.api import AccessToken, VideoGrants

        # Build an admin token to call the SendData API
        token_builder = AccessToken(API_KEY, API_SECRET)
        token_builder.with_grants(VideoGrants(room=room, room_admin=True, room_join=True))
        token_builder.with_identity("recording_controller")
        token = token_builder.to_jwt()

        # Use LiveKit REST API to send data to all participants
        host = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{host}/twirp/livekit.RoomService/SendData",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "room": room,
                    "data": json.dumps(payload).encode().hex(),
                    "kind": 1,  # RELIABLE
                },
                timeout=5.0,
            )
            if resp.status_code != 200:
                print(f"[RECORDING] LiveKit SendData warning: {resp.text}")
    except Exception as e:
        # Non-fatal — ML agent also polls DB as fallback
        print(f"[RECORDING] LiveKit broadcast skipped: {e}")


@router.post("/start", response_model=RecordingResponse)
async def start_recording(room: str, triggered_by: str, db: Session = Depends(get_db)):
    """
    Start recording for a room. Any active participant can trigger this.
    The ML agent receives a LiveKit data message and begins saving WAV files.
    """
    # Check if already recording
    active = db.query(Recording).filter(
        Recording.room_name == room,
        Recording.status == RecordingStatus.active
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="Recording already active for this room")

    rec = Recording(room_name=room, triggered_by=triggered_by)
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Notify ML agent via LiveKit data channel
    await _send_livekit_data(room, {
        "type": "recording_start",
        "recording_id": str(rec.id),
        "triggered_by": triggered_by,
    })

    print(f"[RECORDING] ▶ Started recording in room '{room}' by '{triggered_by}' (id={rec.id})")
    return rec


@router.post("/stop", response_model=RecordingResponse)
async def stop_recording(room: str, file_paths: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Stop active recording for a room.
    ML agent calls this endpoint with the saved file paths when it finishes writing.
    """
    rec = db.query(Recording).filter(
        Recording.room_name == room,
        Recording.status == RecordingStatus.active
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="No active recording found for this room")

    rec.status = RecordingStatus.stopped
    rec.stopped_at = datetime.utcnow()
    rec.file_paths = file_paths
    db.commit()
    db.refresh(rec)

    # Notify ML agent to stop recording
    await _send_livekit_data(room, {"type": "recording_stop"})

    print(f"[RECORDING] ⏹ Stopped recording in room '{room}' (id={rec.id}), files: {file_paths}")
    return rec


@router.get("/status")
def get_recording_status(room: str, db: Session = Depends(get_db)):
    """Check if a room is currently being recorded. ML agent polls this as fallback."""
    active = db.query(Recording).filter(
        Recording.room_name == room,
        Recording.status == RecordingStatus.active
    ).first()
    return {
        "room": room,
        "is_recording": active is not None,
        "recording_id": str(active.id) if active else None,
        "triggered_by": active.triggered_by if active else None,
        "started_at": active.started_at.isoformat() if active else None,
    }


@router.get("/list", response_model=List[RecordingResponse])
def list_recordings(db: Session = Depends(get_db)):
    """List all recordings (for fine-tuning dataset review)."""
    return db.query(Recording).order_by(Recording.started_at.desc()).limit(100).all()
