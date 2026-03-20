from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID, uuid4

from database import get_db
from models import Call, User, Participant
from schemas import CallStartRequest, CallResponse

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.post("/start", response_model=CallResponse)
def start_call(body: CallStartRequest, db: Session = Depends(get_db)):
    """Create a new call room for a company. The created_by user must belong to that company."""
    user = db.get(User, body.created_by)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.company_id != body.company_id:
        raise HTTPException(status_code=403, detail="User does not belong to this company")

    # Generate a unique room name
    room_name = f"call_{uuid4().hex[:12]}"

    call = Call(
        company_id=body.company_id,
        room_name=room_name,
        created_by=body.created_by,
    )
    db.add(call)

    # Automatically add creator as first participant
    participant = Participant(call_id=call.id, user_id=body.created_by)
    db.add(participant)

    db.commit()
    db.refresh(call)
    return call


@router.post("/{call_id}/end", response_model=CallResponse)
def end_call(call_id: UUID, db: Session = Depends(get_db)):
    """Mark a call as ended."""
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.ended_at:
        raise HTTPException(status_code=400, detail="Call already ended")

    call.ended_at = datetime.utcnow()

    # Mark all participants as having left
    for p in call.participants:
        if p.left_at is None:
            p.left_at = call.ended_at

    db.commit()
    db.refresh(call)
    return call


@router.get("/{call_id}", response_model=CallResponse)
def get_call(call_id: UUID, db: Session = Depends(get_db)):
    """Fetch a call by its ID."""
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
