from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from database import Base


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    plan_type = Column(Enum(PlanType), default=PlanType.free)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    calls = relationship("Call", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.member)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users")
    participants = relationship("Participant", back_populates="user")


class Call(Base):
    __tablename__ = "calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    room_name = Column(String, unique=True, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="calls")
    participants = relationship("Participant", back_populates="call")
    ml_events = relationship("MLEvent", back_populates="call")


class Participant(Base):
    __tablename__ = "participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)

    call = relationship("Call", back_populates="participants")
    user = relationship("User", back_populates="participants")


class MLEvent(Base):
    __tablename__ = "ml_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    speaker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    fake_probability = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", back_populates="ml_events")
