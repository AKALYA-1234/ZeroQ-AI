from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database.connection import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from app.models.user import User
from app.models.notification import CustomerProfile
from app.schemas.auth import UserRegister, UserLogin, Token
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/register", response_model=Token)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = get_password_hash(user_data.password)
    user = User(email=user_data.email, hashed_password=hashed_pw, role="customer")
    db.add(user)
    db.flush()
    
    profile = CustomerProfile(
        user_id=user.id,
        full_name=user_data.full_name,
        organization=user_data.organization,
        contact_number=user_data.contact_number
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        email=user.email,
        full_name=user_data.full_name
    )

@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")
    
    full_name = "Quality Admin" if user.role in ["admin", "quality_manager"] else user.email
    if user.customer_profile and user.customer_profile.full_name:
        full_name = user.customer_profile.full_name
    
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        email=user.email,
        full_name=full_name
    )

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    full_name = "Quality Admin" if current_user.role in ["admin", "quality_manager"] else current_user.email
    if current_user.customer_profile and current_user.customer_profile.full_name:
        full_name = current_user.customer_profile.full_name
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "full_name": full_name,
        "created_at": current_user.created_at
    }

@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}
