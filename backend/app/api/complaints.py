from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import os, uuid, shutil
from app.database.connection import get_db
from app.core.dependencies import get_current_customer, get_current_user
from app.core.config import settings
from app.models.complaint import Complaint, ComplaintAttachment, ComplaintStatusHistory
from app.models.product import Product
from app.models.user import User
from app.models.notification import CustomerProfile, ModelPrediction
from app.ml.model_service import is_model_available, predict_complaint_risk

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

def generate_complaint_id(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.query(func.count(Complaint.id)).filter(
        func.extract('year', Complaint.submitted_date) == year,
        Complaint.record_type == "customer_submitted"
    ).scalar() or 0
    return f"ZQ-{year}-{(count + 1):06d}"

@router.post("/")
@router.post("")
async def submit_complaint(
    product_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    reported_severity: str = Form(...),
    batch_number: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    date_of_issue: Optional[str] = Form(None),
    place_of_purchase: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    
    complaint_id = generate_complaint_id(db)
    
    complaint = Complaint(
        complaint_id=complaint_id,
        record_type="customer_submitted",
        submitted_by_user_id=current_user.id,
        customer_name=profile.full_name if profile else None,
        customer_email=current_user.email,
        customer_contact=profile.contact_number if profile else None,
        customer_organization=profile.organization if profile else None,
        product_id=product_id,
        title=title,
        description=description,
        category=category,
        reported_severity=reported_severity,
        place_of_purchase=place_of_purchase,
        purchase_date=datetime.fromisoformat(purchase_date) if purchase_date else None,
        date_of_issue=datetime.fromisoformat(date_of_issue) if date_of_issue else None,
        status="submitted"
    )
    db.add(complaint)
    db.flush()
    
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=None,
        new_status="submitted",
        changed_by=current_user.email,
        changed_by_role="customer",
        notes="Complaint submitted by customer",
        is_customer_visible=True
    )
    db.add(history)
    
    upload_errors = []
    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            upload_errors.append(f"{file.filename}: Invalid file type")
            continue
        
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            upload_errors.append(f"{file.filename}: File too large")
            continue
        
        safe_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
        
        attachment = ComplaintAttachment(
            complaint_id=complaint.id,
            filename=safe_name,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            content_type=file.content_type
        )
        db.add(attachment)

    # ── AI Model Risk Evaluation (Automated) ─────────────────────────
    ai_prediction = None
    if is_model_available():
        try:
            ai_prediction = predict_complaint_risk(
                product_name=product.name if product else None,
                complaint_category=category,
                severity=reported_severity,
                description=description,
                title=title,
                batch_id=batch_number,
            )
            if ai_prediction.get("status") == "success":
                complaint.admin_severity = ai_prediction.get("predicted_severity")
                pred_rec = ModelPrediction(
                    prediction_id=f"PRED-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}",
                    model_version=ai_prediction.get("model_version"),
                    input_features={
                        "product": product.name if product else None,
                        "category": category,
                        "severity": reported_severity,
                        "complaint_id": complaint.complaint_id,
                    },
                    prediction_result=ai_prediction,
                    confidence_score=str(ai_prediction.get("confidence")),
                    created_by=current_user.id,
                )
                db.add(pred_rec)
        except Exception as e:
            pass
    
    db.commit()
    db.refresh(complaint)
    
    return {
        "complaint_id": complaint.complaint_id,
        "id": complaint.id,
        "status": complaint.status,
        "submitted_date": complaint.submitted_date,
        "message": "Complaint submitted successfully",
        "upload_warnings": upload_errors
    }

@router.get("/summary")
def get_complaint_summary(current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    base = db.query(Complaint).filter(Complaint.submitted_by_user_id == current_user.id)
    total = base.count()
    under_review = base.filter(Complaint.status.in_(["under_review", "investigation_in_progress"])).count()
    resolved = base.filter(Complaint.status == "resolved").count()
    return {"total": total, "under_review": under_review, "resolved": resolved}

@router.get("/recent")
def get_recent_complaints(current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaints = db.query(Complaint).filter(
        Complaint.submitted_by_user_id == current_user.id
    ).order_by(Complaint.submitted_date.desc()).limit(3).all()
    
    result = []
    for c in complaints:
        result.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "product_name": c.product.name if c.product else "Unknown",
            "category": c.category,
            "submitted_date": c.submitted_date,
            "status": c.status,
            "reported_severity": c.reported_severity
        })
    return result

@router.get("/")
@router.get("/my-complaints")
def list_complaints(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    query = db.query(Complaint).filter(Complaint.submitted_by_user_id == current_user.id)
    
    if status:
        query = query.filter(Complaint.status == status)
    if category:
        query = query.filter(Complaint.category == category)
    if search:
        query = query.filter(
            (Complaint.complaint_id.ilike(f"%{search}%")) |
            (Complaint.title.ilike(f"%{search}%"))
        )
    
    total = query.count()
    complaints = query.order_by(Complaint.submitted_date.desc()).offset((page-1)*per_page).limit(per_page).all()
    
    result = []
    for c in complaints:
        result.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "product_name": c.product.name if c.product else "Unknown",
            "product_id": c.product_id,
            "category": c.category,
            "title": c.title,
            "reported_severity": c.reported_severity,
            "status": c.status,
            "submitted_date": c.submitted_date,
            "last_updated": c.last_updated
        })
    
    return {
        "items": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

@router.get("/{complaint_id}")
def get_complaint(complaint_id: str, current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.submitted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "product_name": complaint.product.name if complaint.product else "Unknown",
        "product_code": complaint.product.product_id if complaint.product else None,
        "category": complaint.category,
        "title": complaint.title,
        "description": complaint.description,
        "reported_severity": complaint.reported_severity,
        "place_of_purchase": complaint.place_of_purchase,
        "purchase_date": complaint.purchase_date,
        "date_of_issue": complaint.date_of_issue,
        "status": complaint.status,
        "submitted_date": complaint.submitted_date,
        "last_updated": complaint.last_updated,
        "resolved_date": complaint.resolved_date,
        "customer_visible_update": complaint.customer_visible_update,
        "attachments": [
            {
                "id": a.id,
                "original_filename": a.original_filename,
                "file_size": a.file_size,
                "content_type": a.content_type,
                "uploaded_at": a.uploaded_at,
                "url": f"/uploads/{a.filename}"
            }
            for a in complaint.attachments
        ]
    }

@router.get("/{complaint_id}/timeline")
def get_complaint_timeline(complaint_id: str, current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.submitted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    status_map = {
        "submitted": 1,
        "under_review": 2,
        "investigation_in_progress": 3,
        "corrective_action_initiated": 4,
        "resolved": 5,
        "rejected": 5
    }
    current_stage = status_map.get(complaint.status, 1)
    
    history = db.query(ComplaintStatusHistory).filter(
        ComplaintStatusHistory.complaint_id == complaint.id,
        ComplaintStatusHistory.is_customer_visible == True
    ).order_by(ComplaintStatusHistory.changed_at).all()
    
    return {
        "current_status": complaint.status,
        "current_stage": current_stage,
        "total_stages": 5,
        "customer_visible_update": complaint.customer_visible_update,
        "last_updated": complaint.last_updated,
        "history": [
            {
                "status": h.new_status,
                "notes": h.notes,
                "changed_at": h.changed_at
            }
            for h in history
        ]
    }
