from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from database import get_db
from models import Company, User
from schemas import CompanyCreate, CompanyResponse, UserCreate, UserResponse

router = APIRouter(tags=["Companies & Users"])


# ─── Companies ────────────────────────────────────────────

@router.post("/companies", response_model=CompanyResponse)
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new tenant company."""
    company = Company(name=body.name, plan_type=body.plan_type)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(company_id: UUID, db: Session = Depends(get_db)):
    """Get a company by ID."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# ─── Users ────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    """Create a new user belonging to a company."""
    company = db.get(Company, body.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        company_id=body.company_id,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """Get a user by ID."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
