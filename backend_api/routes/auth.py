from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from database import get_db
from models import User, Call
from schemas import TokenResponse
from services.token_service import generate_livekit_token
import os

router = APIRouter(prefix="/token", tags=["Token"])

LIVEKIT_URL = os.getenv("LIVEKIT_PUBLIC_URL", "ws://localhost:7880")


@router.get("", response_model=TokenResponse)
def get_token(user_id: UUID, call_id: UUID, db: Session = Depends(get_db)):
    """
    Issue a LiveKit JWT token for a specific user joining a specific call.
    Enforces company-level isolation: user and call must belong to the same company.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if user.company_id != call.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access denied")

    if call.ended_at is not None:
        raise HTTPException(status_code=400, detail="Call has already ended")

    token = generate_livekit_token(
        identity=str(user.id),
        room=call.room_name,
        name=user.display_name
    )

    return TokenResponse(token=token, livekit_url=LIVEKIT_URL, room_name=call.room_name)
