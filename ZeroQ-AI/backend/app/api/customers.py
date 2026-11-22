from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database.connection import get_db
from app.core.dependencies import get_current_customer
from app.core.security import verify_password, get_password_hash, password_policy_error
from app.models.user import User
from app.models.notification import CustomerProfile, ModelPrediction
from app.schemas.customer import CustomerProfileUpdate, CustomerProfileResponse, PasswordChange, NotificationPreferences
from app.ml.model_service import evaluate_nlp_query

router = APIRouter()

class NLPQueryRequest(BaseModel):
    query: str

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
        "full_name": profile.full_name or "Quality Customer",
        "contact_number": profile.contact_number or "",
        "organization": profile.organization or "Enterprise Client",
        "job_title": profile.job_title or "Quality Manager",
        "country": profile.country or "India",
        "city": profile.city or "",
        "address": profile.address or "",
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
    reason = password_policy_error(pw_data.new_password)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    
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
    return {"message": "Notification preferences updated successfully"}


# ── Phase 3: NLP Query Pipeline Endpoints ─────────────────────────────────

@router.post("/query-prediction")
def submit_query_prediction(
    body: NLPQueryRequest,
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    User Panel Natural Language Query Prediction:
    Extracts entities -> executes model prediction -> persists to DB -> returns result + explanation.
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    result = evaluate_nlp_query(body.query.strip(), user_id=current_user.id, db_session=db)
    return result


@router.get("/query-predictions/history")
def get_query_predictions_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Returns persistent query history for the current user.
    """
    preds = db.query(ModelPrediction).filter(
        ModelPrediction.created_by == current_user.id,
        ModelPrediction.raw_query.isnot(None)
    ).order_by(ModelPrediction.created_at.desc()).limit(limit).all()

    items = []
    for p in preds:
        res = p.prediction_result or {}
        items.append({
            "prediction_id": p.prediction_id,
            "raw_query": p.raw_query,
            "parsed_fields": p.parsed_fields,
            "parse_confidence": p.parse_confidence,
            "prediction": res.get("prediction"),
            "risk_level": res.get("risk_level", "Low"),
            "predicted_severity": res.get("predicted_severity", "low"),
            "complaint_probability": res.get("complaint_probability"),
            "confidence": p.confidence_score,
            "explanation": p.explanation or res.get("explanation"),
            "contributing_factors": res.get("contributing_factors", []),
            "created_at": p.created_at.isoformat() if p.created_at else None
        })

    return {"total": len(items), "items": items}
