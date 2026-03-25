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


@router.get("/demo", response_model=TokenResponse)
def get_demo_token(room: str = "testroom", db: Session = Depends(get_db)):
    """
    Helper route for instantly testing frontends. 
    It automatically provisions a user and wires them into the requested room.
    """
    from models import Company, Participant
    import uuid

    # 1. Reuse or create a demo company
    company = db.query(Company).filter(Company.name == "Demo Corp").first()
    if not company:
        company = Company(name="Demo Corp")
        db.add(company)
        db.flush()

    # 2. Create a fresh user for this caller
    user = User(
        company_id=company.id, 
        email=f"demo_{uuid.uuid4().hex[:6]}@demo.com", 
        display_name=f"Tester {uuid.uuid4().hex[:4]}"
    )
    db.add(user)
    db.flush()

    # 3. Find existing active call for this room, or create a new one
    call = db.query(Call).filter(Call.room_name == room, Call.ended_at == None).first()
    if not call:
        call = Call(company_id=company.id, room_name=room, created_by=user.id)
        db.add(call)
        db.flush()

    # 4. Add participant
    participant = Participant(call_id=call.id, user_id=user.id)
    db.add(participant)
    db.commit()

    token = generate_livekit_token(identity=str(user.id), room=call.room_name, name=user.display_name)
    return TokenResponse(token=token, livekit_url=LIVEKIT_URL, room_name=call.room_name)
