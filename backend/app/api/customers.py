from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.dependencies import get_current_customer
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.models.notification import CustomerProfile
from app.schemas.customer import CustomerProfileUpdate, CustomerProfileResponse, PasswordChange, NotificationPreferences

router = APIRouter()

@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    if not profile:
        profile = CustomerProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "email": current_user.email,
        "full_name": profile.full_name,
        "contact_number": profile.contact_number,
        "organization": profile.organization,
        "job_title": profile.job_title,
        "country": profile.country,
        "city": profile.city,
        "address": profile.address,
        "pref_complaint_submission": profile.pref_complaint_submission,
        "pref_status_updates": profile.pref_status_updates,
        "pref_investigation_updates": profile.pref_investigation_updates,
        "pref_resolution": profile.pref_resolution,
        "pref_email": profile.pref_email,
        "account_status": "active" if current_user.is_active else "inactive",
        "member_since": current_user.created_at,
        "customer_id": f"CUST-{current_user.id:06d}",
        "account_type": "customer"
    }

@router.put("/profile")
def update_profile(
    update_data: CustomerProfileUpdate,
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    if not profile:
        profile = CustomerProfile(user_id=current_user.id)
        db.add(profile)
    
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return {"message": "Profile updated successfully"}

@router.put("/change-password")
def change_password(
    pw_data: PasswordChange,
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    if not verify_password(pw_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(pw_data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    
    current_user.hashed_password = get_password_hash(pw_data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@router.get("/notification-preferences")
def get_notification_prefs(current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    if not profile:
        return NotificationPreferences()
    return {
        "pref_complaint_submission": profile.pref_complaint_submission,
        "pref_status_updates": profile.pref_status_updates,
        "pref_investigation_updates": profile.pref_investigation_updates,
        "pref_resolution": profile.pref_resolution,
        "pref_email": profile.pref_email,
    }

@router.put("/notification-preferences")
def update_notification_prefs(
    prefs: NotificationPreferences,
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    if not profile:
        profile = CustomerProfile(user_id=current_user.id)
        db.add(profile)
    
    profile.pref_complaint_submission = prefs.pref_complaint_submission
    profile.pref_status_updates = prefs.pref_status_updates
    profile.pref_investigation_updates = prefs.pref_investigation_updates
    profile.pref_resolution = prefs.pref_resolution
    profile.pref_email = prefs.pref_email
    db.commit()
    return {"message": "Notification preferences updated"}
