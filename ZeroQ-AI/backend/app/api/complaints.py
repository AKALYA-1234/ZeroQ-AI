from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import os
import uuid
from app.database.connection import get_db
from app.core.dependencies import get_current_customer, get_current_user
from app.core.config import settings
from app.core import rate_limit
from app.intelligence.taxonomy import SEVERITIES
from app.models.complaint import Complaint, ComplaintAttachment, ComplaintStatusHistory
from app.models.product import Product, ProductionBatch
from app.models.user import User
from app.models.notification import CustomerProfile
from app.models.intelligence import IssueAnalysis, IncidentResolution, ResolutionFeedback
from app.api.intelligence import analyze_complaint_job, serialize_analysis, serialize_resolution
from app.intelligence.realtime import broker, complaint_event_payload

MAX_DESCRIPTION_CHARS = 8000
SATISFIED_MIN_RATING = 4

router = APIRouter()
logger = logging.getLogger(__name__)

# Accepted attachment types, identified by content (magic bytes), not by the client's claim.
FILE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".pdf": (b"%PDF-", "application/pdf"),
}
MAX_FILES_PER_COMPLAINT = 5
ID_COLLISION_RETRIES = 5


def _assign_complaint_id(db: Session, complaint: Complaint) -> None:
    """Derive the public ID from the primary key (unique by construction); if an imported
    record already uses that code, add a random suffix. The unique index is the final guard."""
    candidate = f"CMP{complaint.id:06d}"
    for _ in range(ID_COLLISION_RETRIES):
        if not db.query(Complaint.id).filter(Complaint.complaint_id == candidate).first():
            complaint.complaint_id = candidate
            return
        candidate = f"CMP{complaint.id:06d}-{uuid.uuid4().hex[:4].upper()}"
    raise HTTPException(status_code=503, detail="Could not allocate a complaint ID; please retry")


def _parse_optional_date(value: Optional[str], field: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} must be an ISO date (YYYY-MM-DD)")


def _store_upload(file: UploadFile, complaint_pk: int, written: List[str]):
    """Validate and store one upload. Returns (attachment, None) or (None, warning)."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in FILE_SIGNATURES:
        return None, f"{file.filename}: Invalid file type"
    limit = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    content = file.file.read(limit + 1)          # bounded read: never buffers more than the limit
    if len(content) > limit:
        return None, f"{file.filename}: File too large"
    signature, mime = FILE_SIGNATURES[ext]
    if not content.startswith(signature):
        return None, f"{file.filename}: File content does not match its type"
    safe_name = f"{uuid.uuid4()}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as fh:
        fh.write(content)
    written.append(file_path)
    return ComplaintAttachment(complaint_id=complaint_pk, filename=safe_name,
                               original_filename=os.path.basename(file.filename)[:255],
                               file_path=file_path, file_size=len(content), content_type=mime), None


@router.post("/")
@router.post("")
def submit_complaint(
    background_tasks: BackgroundTasks,
    product_id: int = Form(...),
    title: str = Form(..., max_length=500),
    description: str = Form(..., max_length=MAX_DESCRIPTION_CHARS),
    category: Optional[str] = Form(None, max_length=100),
    reported_severity: Optional[str] = Form(None, max_length=20),
    batch_number: Optional[str] = Form(None, max_length=100),
    purchase_date: Optional[str] = Form(None),
    date_of_issue: Optional[str] = Form(None),
    place_of_purchase: Optional[str] = Form(None, max_length=255),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    # Sync handler: FastAPI runs it in the thread pool, so DB / file I/O never blocks the event loop.
    rate_limit.hit(f"submit:{current_user.id}", rate_limit.SUBMIT_LIMIT)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not title.strip() or not description.strip():
        raise HTTPException(status_code=422, detail="Title and description are required")
    if len([f for f in files if f.filename]) > MAX_FILES_PER_COMPLAINT:
        raise HTTPException(status_code=422, detail=f"At most {MAX_FILES_PER_COMPLAINT} attachments")
    # Empty category / severity mean "let the AI identify it".
    category = (category or "").strip() or None
    reported_severity = (reported_severity or "").strip().lower() or None
    if reported_severity and reported_severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail="Invalid severity")
    purchase = _parse_optional_date(purchase_date, "purchase_date")
    issue_date = _parse_optional_date(date_of_issue, "date_of_issue")

    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == current_user.id).first()
    batch = None
    if batch_number and batch_number.strip():
        batch = db.query(ProductionBatch).filter(ProductionBatch.batch_id == batch_number.strip().upper()).first()

    complaint = Complaint(
        record_type="customer_submitted",
        submitted_by_user_id=current_user.id,
        customer_name=profile.full_name if profile else None,
        customer_email=current_user.email,
        customer_contact=profile.contact_number if profile else None,
        customer_organization=profile.organization if profile else None,
        product_id=product_id,
        batch_id=batch.id if batch else None,
        facility_id=batch.facility_id if batch else None,
        title=title.strip(),
        description=description.strip(),
        category=category,
        reported_severity=reported_severity,
        place_of_purchase=place_of_purchase,
        purchase_date=purchase,
        date_of_issue=issue_date,
        status="submitted"
    )
    written: List[str] = []
    upload_errors: List[str] = []
    try:
        db.add(complaint)
        db.flush()
        _assign_complaint_id(db, complaint)
        db.add(ComplaintStatusHistory(
            complaint_id=complaint.id, old_status=None, new_status="submitted",
            changed_by=current_user.email, changed_by_role="customer",
            notes="Complaint submitted by customer", is_customer_visible=True))
        for file in files:
            if not file.filename:
                continue
            attachment, warning = _store_upload(file, complaint.id, written)
            if warning:
                upload_errors.append(warning)
            else:
                db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        for path in written:  # don't leave orphaned files behind a failed transaction
            try:
                os.remove(path)
            except OSError:
                logger.warning("Could not remove orphaned upload %s", path)
        raise
    db.refresh(complaint)

    # Multilingual understanding + prediction runs after the response is sent.
    background_tasks.add_task(analyze_complaint_job, db.get_bind(), complaint.id)
    broker.publish("complaint.created", complaint_event_payload(complaint, {
        "product": product.name, "title": complaint.title}), to_admins=True)

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

def _owned_complaint(db: Session, complaint_id: str, user: User) -> Complaint:
    """Customers may only see complaints they submitted. Anything else is a 404 (not 403),
    so complaint IDs cannot be enumerated."""
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint or complaint.submitted_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.get("/{complaint_id}/attachments/{attachment_id}")
def download_attachment(complaint_id: str, attachment_id: int,
                        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Authenticated attachment download: the complaint owner or an admin."""
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    is_admin = current_user.role in ("admin", "quality_manager")
    if not complaint or (not is_admin and complaint.submitted_by_user_id != current_user.id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    att = db.query(ComplaintAttachment).filter(
        ComplaintAttachment.id == attachment_id, ComplaintAttachment.complaint_id == complaint.id).first()
    upload_root = os.path.realpath(settings.UPLOAD_DIR)
    path = os.path.realpath(att.file_path) if att else ""
    if not att or not path.startswith(upload_root + os.sep) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(path, media_type=att.content_type, filename=att.original_filename,
                        headers={"X-Content-Type-Options": "nosniff",
                                 "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.get("/{complaint_id}")
def get_complaint(complaint_id: str, current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaint = _owned_complaint(db, complaint_id, current_user)
    
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
        "version": complaint.last_updated.isoformat() if complaint.last_updated else None,
        **_intelligence_view(db, complaint),
        "attachments": [
            {
                "id": a.id,
                "original_filename": a.original_filename,
                "file_size": a.file_size,
                "content_type": a.content_type,
                "uploaded_at": a.uploaded_at,
                "url": f"/api/complaints/{complaint.complaint_id}/attachments/{a.id}"
            }
            for a in complaint.attachments
        ]
    }

def _intelligence_view(db: Session, complaint: Complaint) -> dict:
    analysis = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == complaint.id).first()
    resolution = db.query(IncidentResolution).filter(IncidentResolution.complaint_id == complaint.id).first()
    feedback = db.query(ResolutionFeedback).filter(ResolutionFeedback.complaint_id == complaint.id).first()
    return {
        "ai_understanding": serialize_analysis(analysis, audience="customer"),
        "resolution": serialize_resolution(resolution, audience="customer"),
        "feedback": {"rating": feedback.rating, "satisfied": feedback.satisfied, "comment": feedback.comment,
                     "created_at": feedback.created_at.isoformat()} if feedback else None,
    }


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)


@router.post("/{complaint_id}/feedback")
def submit_feedback(complaint_id: str, body: FeedbackRequest,
                    current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.submitted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if complaint.status != "resolved":
        raise HTTPException(status_code=409, detail="Feedback is accepted once the complaint is resolved")
    fb = ResolutionFeedback(complaint_id=complaint.id, user_id=current_user.id, rating=body.rating,
                            satisfied=body.rating >= SATISFIED_MIN_RATING,
                            comment=(body.comment or "").strip() or None)
    db.add(fb)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Feedback already submitted")
    broker.publish("feedback.submitted", complaint_event_payload(complaint, {"rating": body.rating}),
                   to_admins=True)
    return {"rating": fb.rating, "satisfied": fb.satisfied, "comment": fb.comment}


@router.get("/{complaint_id}/timeline")
def get_complaint_timeline(complaint_id: str, current_user: User = Depends(get_current_customer), db: Session = Depends(get_db)):
    complaint = _owned_complaint(db, complaint_id, current_user)
    
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
