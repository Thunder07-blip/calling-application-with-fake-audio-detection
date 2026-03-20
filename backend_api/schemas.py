from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
import enum


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


# ─── Company ─────────────────────────────────────────────
class CompanyCreate(BaseModel):
    name: str
    plan_type: Optional[PlanType] = PlanType.free


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    plan_type: PlanType
    created_at: datetime

    class Config:
        from_attributes = True


# ─── User ─────────────────────────────────────────────────
class UserCreate(BaseModel):
    company_id: UUID
    email: EmailStr
    display_name: str
    role: Optional[UserRole] = UserRole.member


class UserResponse(BaseModel):
    id: UUID
    company_id: UUID
    email: str
    display_name: str
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Call ─────────────────────────────────────────────────
class CallStartRequest(BaseModel):
    company_id: UUID
    created_by: UUID


class CallResponse(BaseModel):
    id: UUID
    company_id: UUID
    room_name: str
    created_by: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── ML Events ────────────────────────────────────────────
class MLEventCreate(BaseModel):
    call_id: UUID
    speaker_id: Optional[UUID] = None
    fake_probability: float = Field(..., ge=0.0, le=1.0)


class MLEventResponse(BaseModel):
    id: UUID
    call_id: UUID
    speaker_id: Optional[UUID]
    fake_probability: float
    timestamp: datetime

    class Config:
        from_attributes = True


# ─── Token ────────────────────────────────────────────────
class TokenResponse(BaseModel):
    token: str
    livekit_url: str
    room_name: str
