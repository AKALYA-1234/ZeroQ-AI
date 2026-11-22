from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, case, distinct, and_, or_, desc, asc, cast, Float, Integer as SAInteger
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from app.database.connection import get_db
from app.core.dependencies import get_current_admin
from app.models.complaint import Complaint, ComplaintStatusHistory, ComplaintAttachment
from app.models.product import Product, Facility, ProductionBatch, ProductionLine
from app.models.investigation import Investigation
from app.models.corrective_action import CorrectiveAction
from app.models.notification import AuditLog, ModelPrediction
from app.ml.model_service import (
    predict_complaint_risk, is_model_available, get_model_metadata,
    get_feature_importance, get_model_error, MODEL_VERSION,
)
from app.schemas.complaint import ComplaintStatusUpdate
from app.intelligence.realtime import broker, complaint_event_payload
from app.models.intelligence import IssueAnalysis, IncidentResolution

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic helpers
# ---------------------------------------------------------------------------

class InvestigationCreate(BaseModel):
    complaint_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    investigation_type: Optional[str] = "root_cause_analysis"
    root_cause_category: Optional[str] = None
    root_cause_description: Optional[str] = None
    is_root_cause_verified: bool = False
    priority: Optional[str] = "medium"
    status: Optional[str] = "open"

class CAPACreate(BaseModel):
    action_type: str = "corrective"
    title: str
    description: Optional[str] = ""
    priority: str = "medium"
    assigned_to: Optional[str] = ""
    complaint_id: Optional[int] = None
    investigation_id: Optional[int] = None
    deadline: Optional[datetime] = None

class CAPAUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    completion_evidence: Optional[str] = None
    effectiveness_status: Optional[str] = None
    effectiveness_evidence: Optional[str] = None
    deadline: Optional[datetime] = None

class PredictionInput(BaseModel):
    product_id: Optional[int] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    batch_id: Optional[str] = None
    facility: Optional[str] = None
    title: Optional[str] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_severity_case = case(
    (Complaint.reported_severity == "critical", 4),
    (Complaint.reported_severity == "high", 3),
    (Complaint.reported_severity == "medium", 2),
    (Complaint.reported_severity == "low", 1),
    else_=0,
)


def _create_audit_log(db: Session, user, action: str, resource_type: str, resource_id: str, details: dict = None):
    log = AuditLog(
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=details or {},
    )
    db.add(log)


def _complaint_summary(c: Complaint) -> dict:
    return {
        "id": c.id,
        "complaint_id": c.complaint_id,
        "record_type": c.record_type,
        "customer_name": c.customer_name,
        "customer_email": c.customer_email,
        "product_name": c.product.name if c.product else "Unknown",
        "product_category": c.product.category if c.product else None,
        "batch_id": c.batch.batch_id if c.batch else None,
        "category": c.category,
        "title": c.title,
        "reported_severity": c.reported_severity,
        "admin_severity": c.admin_severity,
        "status": c.status,
        "submitted_date": c.submitted_date,
        "last_updated": c.last_updated,
        "resolved_date": c.resolved_date,
        "assigned_to": c.assigned_to,
        "facility_id": c.facility_id,
    }


# =========================================================================
# 1. DASHBOARD
# =========================================================================

@router.get("/dashboard")
def get_dashboard(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    total = db.query(func.count(Complaint.id)).scalar() or 0
    open_c = db.query(func.count(Complaint.id)).filter(
        Complaint.status.notin_(["resolved", "rejected", "closed"])
    ).scalar() or 0
    resolved = db.query(func.count(Complaint.id)).filter(Complaint.status == "resolved").scalar() or 0
    critical_high = db.query(func.count(Complaint.id)).filter(
        Complaint.reported_severity.in_(["critical", "high"])
    ).scalar() or 0

    try:
        if db.bind and db.bind.dialect.name == "sqlite":
            avg_res = db.query(
                func.avg(
                    func.julianday(Complaint.resolved_date) - func.julianday(Complaint.submitted_date)
                )
            ).filter(Complaint.resolved_date.isnot(None), Complaint.submitted_date.isnot(None)).scalar()
            avg_resolution_days = round(float(avg_res or 0), 1)
        else:
            avg_resolution_q = db.query(
                func.avg(
                    func.extract("epoch", Complaint.resolved_date) - func.extract("epoch", Complaint.submitted_date)
                )
            ).filter(Complaint.resolved_date.isnot(None), Complaint.submitted_date.isnot(None)).scalar()
            avg_resolution_days = round((avg_resolution_q or 0) / 86400, 1)
    except Exception:
        avg_resolution_days = 0.0

    # Trend data — by year
    by_year = db.query(
        extract("year", Complaint.submitted_date).label("year"),
        func.count(Complaint.id).label("count"),
    ).group_by("year").order_by("year").all()

    # Monthly distribution (aggregate across all years)
    by_month = db.query(
        extract("month", Complaint.submitted_date).label("month"),
        func.count(Complaint.id).label("count"),
    ).group_by("month").order_by("month").all()

    # Category breakdown
    by_category = db.query(
        Complaint.category,
        func.count(Complaint.id).label("count"),
    ).filter(Complaint.category.isnot(None)).group_by(Complaint.category).order_by(desc("count")).all()

    # Product breakdown (top 10)
    by_product = db.query(
        Product.name,
        func.count(Complaint.id).label("count"),
    ).join(Product, Complaint.product_id == Product.id).group_by(Product.name).order_by(desc("count")).limit(10).all()

    # Recent complaints
    recent = (
        db.query(Complaint)
        .options(joinedload(Complaint.product))
        .order_by(Complaint.submitted_date.desc())
        .limit(10)
        .all()
    )

    # Root cause summary
    root_cause_summary = db.query(
        Investigation.root_cause_category,
        func.count(Investigation.id).label("count"),
    ).filter(Investigation.root_cause_category.isnot(None)).group_by(
        Investigation.root_cause_category
    ).order_by(desc("count")).limit(10).all()

    # Risk / severity distribution
    severity_dist = db.query(
        Complaint.reported_severity,
        func.count(Complaint.id).label("count"),
    ).filter(Complaint.reported_severity.isnot(None)).group_by(Complaint.reported_severity).all()

    return {
        "kpis": {
            "total_complaints": total,
            "open_complaints": open_c,
            "resolved_complaints": resolved,
            "critical_high_count": critical_high,
            "avg_resolution_days": avg_resolution_days,
            "data_note": "Includes synthetic historical records (2008-2026)",
        },
        "complaints_by_year": [{"year": int(r.year), "count": r.count} for r in by_year if r.year],
        "complaints_by_month": [
            {"month": int(r.month), "month_name": MONTH_NAMES[int(r.month)] if int(r.month) <= 12 else str(r.month), "count": r.count}
            for r in by_month if r.month
        ],
        "complaints_by_category": [{"category": r.category, "count": r.count} for r in by_category],
        "complaints_by_product": [{"product": r.name, "count": r.count} for r in by_product],
        "recent_complaints": [
            {
                "complaint_id": c.complaint_id,
                "product_name": c.product.name if c.product else "Unknown",
                "category": c.category,
                "severity": c.reported_severity,
                "status": c.status,
                "submitted_date": c.submitted_date,
                "record_type": c.record_type,
            }
            for c in recent
        ],
        "root_cause_summary": [{"category": r.root_cause_category, "count": r.count} for r in root_cause_summary],
        "risk_distribution": [{"severity": r.reported_severity, "count": r.count} for r in severity_dist],
    }


# =========================================================================
# 2-4. COMPLAINTS (list, detail, update)
# =========================================================================

@router.get("/complaints")
def list_all_complaints(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    record_type: Optional[str] = None,
    product_id: Optional[int] = None,
    facility_id: Optional[int] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: Optional[str] = Query("submitted_date", pattern="^(submitted_date|last_updated|status|reported_severity|category)$"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Complaint).options(joinedload(Complaint.product), joinedload(Complaint.batch))

    if status:
        query = query.filter(Complaint.status == status)
    if category:
        query = query.filter(Complaint.category == category)
    if severity:
        query = query.filter(Complaint.reported_severity == severity)
    if record_type:
        query = query.filter(Complaint.record_type == record_type)
    if product_id:
        query = query.filter(Complaint.product_id == product_id)
    if facility_id:
        query = query.filter(Complaint.facility_id == facility_id)
    if source:
        query = query.filter(Complaint.record_type == source)
    if search:
        search_filter = or_(
            Complaint.complaint_id.ilike(f"%{search}%"),
            Complaint.customer_name.ilike(f"%{search}%"),
            Complaint.title.ilike(f"%{search}%"),
            Complaint.description.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    total = query.count()

    sort_col = getattr(Complaint, sort_by, Complaint.submitted_date)
    order_func = desc if sort_order == "desc" else asc
    complaints = query.order_by(order_func(sort_col)).offset((page - 1) * per_page).limit(per_page).all()

    # One extra query (not N+1) to attach the AI prediction badge for the page.
    analyses = {
        a.complaint_id: a for a in db.query(IssueAnalysis)
        .filter(IssueAnalysis.complaint_id.in_([c.id for c in complaints])).all()
    } if complaints else {}
    items = []
    for c in complaints:
        row = _complaint_summary(c)
        a = analyses.get(c.id)
        row["ai"] = {
            "source": a.prediction_source, "category": a.predicted_category,
            "confidence": a.confidence, "low_confidence": a.is_low_confidence,
            "language": a.language_name,
        } if a else None
        items.append(row)

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/complaints/{complaint_id}")
def get_complaint_detail(
    complaint_id: str,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.product),
            joinedload(Complaint.batch),
            joinedload(Complaint.attachments),
            joinedload(Complaint.status_history),
            joinedload(Complaint.investigations),
            joinedload(Complaint.corrective_actions),
        )
        .filter(Complaint.complaint_id == complaint_id)
        .first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    facility = None
    if complaint.facility_id:
        fac = db.query(Facility).filter(Facility.id == complaint.facility_id).first()
        if fac:
            facility = {"id": fac.id, "facility_id": fac.facility_id, "name": fac.name, "location": fac.location}

    return {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "record_type": complaint.record_type,
        "customer_name": complaint.customer_name,
        "customer_email": complaint.customer_email,
        "customer_contact": complaint.customer_contact,
        "customer_organization": complaint.customer_organization,
        "title": complaint.title,
        "description": complaint.description,
        "category": complaint.category,
        "reported_severity": complaint.reported_severity,
        "admin_severity": complaint.admin_severity,
        "status": complaint.status,
        "submitted_date": complaint.submitted_date,
        "last_updated": complaint.last_updated,
        "resolved_date": complaint.resolved_date,
        "assigned_to": complaint.assigned_to,
        "internal_notes": complaint.internal_notes,
        "customer_visible_update": complaint.customer_visible_update,
        "purchase_date": complaint.purchase_date,
        "date_of_issue": complaint.date_of_issue,
        "place_of_purchase": complaint.place_of_purchase,
        "product": {
            "id": complaint.product.id,
            "product_id": complaint.product.product_id,
            "name": complaint.product.name,
            "category": complaint.product.category,
        } if complaint.product else None,
        "batch": {
            "id": complaint.batch.id,
            "batch_id": complaint.batch.batch_id,
            "lot_number": complaint.batch.lot_number,
            "production_date": complaint.batch.production_date,
            "facility_id": complaint.batch.facility_id,
        } if complaint.batch else None,
        "facility": facility,
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "original_filename": a.original_filename,
                "file_size": a.file_size,
                "content_type": a.content_type,
                "uploaded_at": a.uploaded_at,
            }
            for a in (complaint.attachments or [])
        ],
        "status_history": [
            {
                "id": h.id,
                "old_status": h.old_status,
                "new_status": h.new_status,
                "changed_by": h.changed_by,
                "changed_by_role": h.changed_by_role,
                "notes": h.notes,
                "is_customer_visible": h.is_customer_visible,
                "changed_at": h.changed_at,
            }
            for h in sorted(complaint.status_history or [], key=lambda x: x.changed_at or datetime.min, reverse=True)
        ],
        "investigations": [
            {
                "id": inv.id,
                "investigation_id": inv.investigation_id,
                "title": inv.title,
                "description": inv.description,
                "investigation_type": inv.investigation_type,
                "root_cause_category": inv.root_cause_category,
                "root_cause_description": inv.root_cause_description,
                "is_root_cause_verified": inv.is_root_cause_verified,
                "status": inv.status,
                "priority": inv.priority,
                "opened_date": inv.opened_date,
                "closed_date": inv.closed_date,
            }
            for inv in (complaint.investigations or [])
        ],
        "corrective_actions": [
            {
                "id": ca.id,
                "capa_id": ca.capa_id,
                "action_type": ca.action_type,
                "title": ca.title,
                "description": ca.description,
                "priority": ca.priority,
                "status": ca.status,
                "assigned_to": ca.assigned_to,
                "deadline": ca.deadline,
                "effectiveness_status": ca.effectiveness_status,
                "created_at": ca.created_at,
                "completed_at": ca.completed_at,
            }
            for ca in (complaint.corrective_actions or [])
        ],
    }


@router.put("/complaints/{complaint_id}")
def update_complaint(
    complaint_id: str,
    update_data: ComplaintStatusUpdate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status = complaint.status
    changes: dict = {}
    if update_data.status and update_data.status != "resolved" and db.query(IncidentResolution.id).filter(
            IncidentResolution.complaint_id == complaint.id).first():
        # Verified resolutions are ground truth for analytics and training; reopening would leave
        # a "resolved" record behind an open complaint.
        raise HTTPException(status_code=409, detail="This complaint has a verified resolution and cannot be reopened")

    if update_data.status:
        complaint.status = update_data.status
        changes["status"] = {"old": old_status, "new": update_data.status}
        if update_data.status == "resolved":
            complaint.resolved_date = datetime.utcnow()
    if update_data.assigned_to:
        changes["assigned_to"] = {"old": complaint.assigned_to, "new": update_data.assigned_to}
        complaint.assigned_to = update_data.assigned_to
    if update_data.admin_severity:
        changes["admin_severity"] = {"old": complaint.admin_severity, "new": update_data.admin_severity}
        complaint.admin_severity = update_data.admin_severity
    if update_data.internal_notes:
        complaint.internal_notes = update_data.internal_notes
    if update_data.customer_visible_update:
        complaint.customer_visible_update = update_data.customer_visible_update

    complaint.last_updated = datetime.utcnow()

    # Status history entry
    if old_status != complaint.status or update_data.notes:
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=old_status,
            new_status=complaint.status,
            changed_by=current_user.email,
            changed_by_role=current_user.role,
            notes=update_data.notes,
            is_customer_visible=update_data.is_customer_visible,
        )
        db.add(history)

    # Audit log
    _create_audit_log(db, current_user, "update_complaint", "complaint", complaint_id, changes)

    db.commit()
    db.refresh(complaint)
    broker.publish("complaint.updated", complaint_event_payload(complaint, {
        "customer_visible_update": complaint.customer_visible_update if update_data.is_customer_visible else None}),
        user_ids=[complaint.submitted_by_user_id], to_admins=True)
    return {"message": "Complaint updated successfully", "complaint_id": complaint_id}


# =========================================================================
# 5-6. ANALYTICS
# =========================================================================

@router.get("/analytics")
def get_analytics(
    year: Optional[int] = None,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    base_q = db.query(Complaint)
    if year:
        base_q = base_q.filter(extract("year", Complaint.submitted_date) == year)

    # By year
    by_year = db.query(
        extract("year", Complaint.submitted_date).label("year"),
        func.count(Complaint.id).label("count"),
    ).group_by("year").order_by("year").all()

    # By month (within filtered year or all)
    month_q = db.query(
        extract("year", Complaint.submitted_date).label("year"),
        extract("month", Complaint.submitted_date).label("month"),
        func.count(Complaint.id).label("count"),
    )
    if year:
        month_q = month_q.filter(extract("year", Complaint.submitted_date) == year)
    by_month = month_q.group_by("year", "month").order_by("year", "month").all()

    # By category
    cat_q = db.query(Complaint.category, func.count(Complaint.id).label("count")).filter(Complaint.category.isnot(None))
    if year:
        cat_q = cat_q.filter(extract("year", Complaint.submitted_date) == year)
    by_category = cat_q.group_by(Complaint.category).order_by(desc("count")).all()

    # By severity
    sev_q = db.query(Complaint.reported_severity, func.count(Complaint.id).label("count")).filter(Complaint.reported_severity.isnot(None))
    if year:
        sev_q = sev_q.filter(extract("year", Complaint.submitted_date) == year)
    by_severity = sev_q.group_by(Complaint.reported_severity).all()

    # By product (top 15)
    prod_q = (
        db.query(Product.name.label("product"), func.count(Complaint.id).label("count"))
        .join(Product, Complaint.product_id == Product.id)
    )
    if year:
        prod_q = prod_q.filter(extract("year", Complaint.submitted_date) == year)
    by_product = prod_q.group_by(Product.name).order_by(desc("count")).limit(15).all()

    # By facility
    fac_q = (
        db.query(Facility.name.label("facility"), func.count(Complaint.id).label("count"))
        .join(Facility, Complaint.facility_id == Facility.id)
    )
    if year:
        fac_q = fac_q.filter(extract("year", Complaint.submitted_date) == year)
    by_facility = fac_q.group_by(Facility.name).order_by(desc("count")).all()

    # By customer (top 15)
    cust_q = db.query(Complaint.customer_name, func.count(Complaint.id).label("count")).filter(Complaint.customer_name.isnot(None))
    if year:
        cust_q = cust_q.filter(extract("year", Complaint.submitted_date) == year)
    by_customer = cust_q.group_by(Complaint.customer_name).order_by(desc("count")).limit(15).all()

    # Product-category heatmap
    heatmap_q = (
        db.query(
            Product.name.label("product"),
            Complaint.category,
            func.count(Complaint.id).label("count"),
        )
        .join(Product, Complaint.product_id == Product.id)
        .filter(Complaint.category.isnot(None))
    )
    if year:
        heatmap_q = heatmap_q.filter(extract("year", Complaint.submitted_date) == year)
    heatmap = heatmap_q.group_by(Product.name, Complaint.category).order_by(desc("count")).limit(50).all()

    # Recurring patterns: categories with > 5 complaints across multiple products
    recurring_q = (
        db.query(
            Complaint.category,
            func.count(Complaint.id).label("complaint_count"),
            func.count(distinct(Complaint.product_id)).label("product_count"),
        )
        .filter(Complaint.category.isnot(None))
    )
    if year:
        recurring_q = recurring_q.filter(extract("year", Complaint.submitted_date) == year)
    recurring_raw = recurring_q.group_by(Complaint.category).having(func.count(Complaint.id) > 5).order_by(desc("complaint_count")).all()

    # Severity trend by year-month
    sev_trend_q = db.query(
        extract("year", Complaint.submitted_date).label("year"),
        extract("month", Complaint.submitted_date).label("month"),
        Complaint.reported_severity,
        func.count(Complaint.id).label("count"),
    ).filter(Complaint.reported_severity.isnot(None))
    if year:
        sev_trend_q = sev_trend_q.filter(extract("year", Complaint.submitted_date) == year)
    severity_trend = sev_trend_q.group_by("year", "month", Complaint.reported_severity).order_by("year", "month").all()

    return {
        "by_year": [{"year": int(r.year), "count": r.count} for r in by_year if r.year],
        "by_month": [
            {"year": int(r.year), "month": int(r.month), "month_name": MONTH_NAMES[int(r.month)] if int(r.month) <= 12 else "", "count": r.count}
            for r in by_month if r.month
        ],
        "by_category": [{"category": r.category, "count": r.count} for r in by_category],
        "by_severity": [{"severity": r.reported_severity, "count": r.count} for r in by_severity],
        "by_product": [{"product": r.product, "count": r.count} for r in by_product],
        "by_facility": [{"facility": r.facility, "count": r.count} for r in by_facility],
        "by_customer": [{"customer": r.customer_name, "count": r.count} for r in by_customer],
        "product_category_heatmap": [
            {"product": r.product, "category": r.category, "count": r.count} for r in heatmap
        ],
        "recurring_patterns": [
            {"category": r.category, "complaint_count": r.complaint_count, "product_count": r.product_count}
            for r in recurring_raw
        ],
        "severity_trend": [
            {
                "year": int(r.year),
                "month": int(r.month),
                "severity": r.reported_severity,
                "count": r.count,
            }
            for r in severity_trend if r.year and r.month
        ],
        "data_note": "Includes synthetic historical records (2008-2026)",
    }


@router.get("/analytics/kpis")
def get_analytics_kpis(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    total = db.query(func.count(Complaint.id)).scalar() or 0

    # Avg monthly: total / distinct months
    distinct_months = db.query(
        func.count(
            distinct(
                func.concat(
                    extract("year", Complaint.submitted_date),
                    "-",
                    extract("month", Complaint.submitted_date),
                )
            )
        )
    ).scalar() or 1
    avg_monthly = round(total / max(distinct_months, 1), 1)

    # Most affected product
    most_product = (
        db.query(Product.name, func.count(Complaint.id).label("cnt"))
        .join(Product, Complaint.product_id == Product.id)
        .group_by(Product.name)
        .order_by(desc("cnt"))
        .first()
    )

    # Most frequent category
    most_category = (
        db.query(Complaint.category, func.count(Complaint.id).label("cnt"))
        .filter(Complaint.category.isnot(None))
        .group_by(Complaint.category)
        .order_by(desc("cnt"))
        .first()
    )

    # High + critical count
    high_critical = db.query(func.count(Complaint.id)).filter(
        Complaint.reported_severity.in_(["critical", "high"])
    ).scalar() or 0

    # Recurring clusters: categories appearing in > 3 products
    clusters = (
        db.query(func.count(Complaint.category))
        .filter(Complaint.category.isnot(None))
        .group_by(Complaint.category)
        .having(func.count(distinct(Complaint.product_id)) > 3)
        .all()
    )

    return {
        "total_complaints": total,
        "avg_monthly": avg_monthly,
        "most_affected_product": most_product.name if most_product else "N/A",
        "most_affected_product_count": most_product.cnt if most_product else 0,
        "most_frequent_category": most_category.category if most_category else "N/A",
        "most_frequent_category_count": most_category.cnt if most_category else 0,
        "high_critical_count": high_critical,
        "recurring_clusters": len(clusters),
    }


# =========================================================================
# 7-10. ROOT CAUSES
# =========================================================================

@router.get("/root-causes")
def get_root_causes(
    status: Optional[str] = None,
    verified: Optional[bool] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Investigation).options(joinedload(Investigation.complaint))

    if status:
        query = query.filter(Investigation.status == status)
    if verified is not None:
        query = query.filter(Investigation.is_root_cause_verified == verified)
    if category:
        query = query.filter(Investigation.root_cause_category == category)

    total = query.count()
    items = query.order_by(Investigation.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": inv.id,
                "investigation_id": inv.investigation_id,
                "complaint_id": inv.complaint.complaint_id if inv.complaint else None,
                "title": inv.title,
                "description": inv.description,
                "investigation_type": inv.investigation_type,
                "root_cause_category": inv.root_cause_category,
                "root_cause_description": inv.root_cause_description,
                "is_root_cause_verified": inv.is_root_cause_verified,
                "status": inv.status,
                "priority": inv.priority,
                "opened_date": inv.opened_date,
                "closed_date": inv.closed_date,
                "created_at": inv.created_at,
            }
            for inv in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "note": "Verified root causes are human-confirmed. AI hypotheses are clearly labeled separately.",
    }


@router.get("/root-causes/frequency")
def get_root_cause_frequency(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Root cause frequency chart data."""
    by_category = (
        db.query(
            Investigation.root_cause_category,
            Investigation.is_root_cause_verified,
            func.count(Investigation.id).label("count"),
        )
        .filter(Investigation.root_cause_category.isnot(None))
        .group_by(Investigation.root_cause_category, Investigation.is_root_cause_verified)
        .order_by(desc("count"))
        .all()
    )

    # Monthly root cause trend
    monthly = (
        db.query(
            extract("year", Investigation.created_at).label("year"),
            extract("month", Investigation.created_at).label("month"),
            Investigation.root_cause_category,
            func.count(Investigation.id).label("count"),
        )
        .filter(Investigation.root_cause_category.isnot(None))
        .group_by("year", "month", Investigation.root_cause_category)
        .order_by("year", "month")
        .all()
    )

    return {
        "by_category": [
            {"category": r.root_cause_category, "is_verified": r.is_root_cause_verified, "count": r.count}
            for r in by_category
        ],
        "monthly_trend": [
            {"year": int(r.year), "month": int(r.month), "category": r.root_cause_category, "count": r.count}
            for r in monthly if r.year and r.month
        ],
    }


@router.get("/root-causes/analysis/{complaint_id}")
def get_root_cause_analysis(
    complaint_id: str,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .options(joinedload(Complaint.product), joinedload(Complaint.investigations))
        .filter(Complaint.complaint_id == complaint_id)
        .first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Investigations for this complaint
    investigations = [
        {
            "id": inv.id,
            "investigation_id": inv.investigation_id,
            "title": inv.title,
            "root_cause_category": inv.root_cause_category,
            "root_cause_description": inv.root_cause_description,
            "is_root_cause_verified": inv.is_root_cause_verified,
            "status": inv.status,
            "priority": inv.priority,
            "opened_date": inv.opened_date,
            "closed_date": inv.closed_date,
        }
        for inv in (complaint.investigations or [])
    ]

    # Similar complaints (same product + category)
    similar_q = db.query(Complaint).options(joinedload(Complaint.product)).filter(
        Complaint.id != complaint.id,
    )
    conditions = []
    if complaint.product_id:
        conditions.append(Complaint.product_id == complaint.product_id)
    if complaint.category:
        conditions.append(Complaint.category == complaint.category)
    if conditions:
        similar_q = similar_q.filter(or_(*conditions))

    similar = similar_q.order_by(Complaint.submitted_date.desc()).limit(10).all()

    # 6M hypotheses (Man, Machine, Material, Method, Measurement, Mother Nature)
    sixm_categories = {
        "Man": "Human error, operator training, fatigue, or skill gaps",
        "Machine": "Equipment malfunction, calibration, or maintenance issues",
        "Material": "Raw material defects, supplier quality, or storage",
        "Method": "Process deviation, SOP non-compliance, or design flaw",
        "Measurement": "Inspection error, gauge issues, or sampling problems",
        "Mother Nature": "Environmental conditions, temperature, humidity",
    }

    # Map existing root causes to 6M
    hypotheses = {}
    for cat_key, cat_desc in sixm_categories.items():
        related_investigations = [
            inv for inv in (complaint.investigations or [])
            if inv.root_cause_category and cat_key.lower() in inv.root_cause_category.lower()
        ]
        hypotheses[cat_key] = {
            "description": cat_desc,
            "has_evidence": len(related_investigations) > 0,
            "investigations": [
                {
                    "investigation_id": inv.investigation_id,
                    "root_cause_description": inv.root_cause_description,
                    "is_verified": inv.is_root_cause_verified,
                }
                for inv in related_investigations
            ],
        }

    return {
        "complaint": _complaint_summary(complaint),
        "investigations": investigations,
        "similar_complaints": [_complaint_summary(s) for s in similar],
        "similar_count": len(similar),
        "hypotheses_6m": hypotheses,
    }


@router.post("/root-causes/investigate")
def start_investigation(
    data: InvestigationCreate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == data.complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Check for existing open investigation
    existing = db.query(Investigation).filter(
        Investigation.complaint_id == complaint.id,
        Investigation.status.in_(["open", "in_progress"]),
    ).first()

    if existing:
        # Update existing investigation
        if data.root_cause_category:
            existing.root_cause_category = data.root_cause_category
        if data.root_cause_description:
            existing.root_cause_description = data.root_cause_description
        if data.is_root_cause_verified is not None:
            existing.is_root_cause_verified = data.is_root_cause_verified
        if data.status:
            existing.status = data.status
            if data.status in ("closed", "completed"):
                existing.closed_date = datetime.utcnow()
        if data.title:
            existing.title = data.title
        if data.description:
            existing.description = data.description

        _create_audit_log(db, current_user, "update_investigation", "investigation", existing.investigation_id, {
            "root_cause_category": data.root_cause_category,
            "status": data.status,
        })
        db.commit()
        return {"message": "Investigation updated", "investigation_id": existing.investigation_id}

    # Create new investigation
    year = datetime.utcnow().year
    count = db.query(func.count(Investigation.id)).scalar() or 0
    inv_id = f"INV-{year}-{(count + 1):04d}"

    investigation = Investigation(
        investigation_id=inv_id,
        complaint_id=complaint.id,
        title=data.title or f"Investigation for {data.complaint_id}",
        description=data.description or "",
        investigation_type=data.investigation_type,
        root_cause_category=data.root_cause_category,
        root_cause_description=data.root_cause_description,
        is_root_cause_verified=data.is_root_cause_verified,
        status=data.status or "open",
        priority=data.priority,
        opened_date=datetime.utcnow(),
        record_type="admin_created",
    )
    db.add(investigation)

    # Update complaint status if still submitted
    if complaint.status in ("submitted", "received"):
        complaint.status = "under_investigation"
        complaint.last_updated = datetime.utcnow()
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status="submitted",
            new_status="under_investigation",
            changed_by=current_user.email,
            changed_by_role=current_user.role,
            notes="Investigation started",
            is_customer_visible=True,
        )
        db.add(history)

    _create_audit_log(db, current_user, "create_investigation", "investigation", inv_id, {
        "complaint_id": data.complaint_id,
        "root_cause_category": data.root_cause_category,
    })

    db.commit()
    return {"message": "Investigation created", "investigation_id": inv_id}


# =========================================================================
# 11-15. RISK ASSESSMENT
# =========================================================================

@router.get("/risk-assessment")
def get_risk_assessment(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Product risk ranking with composite scores."""
    product_risks = (
        db.query(
            Product.id,
            Product.name,
            Product.product_id,
            Product.category,
            func.count(Complaint.id).label("complaint_count"),
            func.sum(_severity_case).label("severity_score"),
            func.count(
                case((Complaint.reported_severity.in_(["critical", "high"]), Complaint.id), else_=None)
            ).label("high_critical_count"),
            func.count(
                case((Complaint.status.notin_(["resolved", "rejected", "closed"]), Complaint.id), else_=None)
            ).label("open_count"),
        )
        .join(Complaint, Product.id == Complaint.product_id, isouter=True)
        .group_by(Product.id, Product.name, Product.product_id, Product.category)
        .order_by(desc("severity_score"))
        .all()
    )

    max_severity = max((float(r.severity_score or 0) for r in product_risks), default=1) or 1
    max_count = max((r.complaint_count or 0 for r in product_risks), default=1) or 1

    results = []
    for r in product_risks:
        count_norm = (r.complaint_count or 0) / max_count
        severity_norm = float(r.severity_score or 0) / max_severity
        risk_score = round((0.4 * count_norm + 0.6 * severity_norm) * 100, 1)
        risk_level = "critical" if risk_score >= 75 else "high" if risk_score >= 50 else "medium" if risk_score >= 25 else "low"
        results.append({
            "product_id": r.product_id,
            "product_name": r.name,
            "product_category": r.category,
            "complaint_count": r.complaint_count or 0,
            "severity_score": float(r.severity_score or 0),
            "high_critical_count": r.high_critical_count or 0,
            "open_count": r.open_count or 0,
            "risk_score": risk_score,
            "risk_level": risk_level,
        })

    return {"product_risks": results}


@router.get("/risk-assessment/batches")
def get_batch_risk_assessment(
    product_id: Optional[int] = None,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Batch-level risk assessment."""
    query = (
        db.query(
            ProductionBatch.id,
            ProductionBatch.batch_id,
            ProductionBatch.lot_number,
            ProductionBatch.production_date,
            ProductionBatch.quantity_produced,
            ProductionBatch.status,
            Product.name.label("product_name"),
            func.count(Complaint.id).label("complaint_count"),
            func.sum(_severity_case).label("severity_score"),
        )
        .join(Product, ProductionBatch.product_id == Product.id, isouter=True)
        .join(Complaint, ProductionBatch.id == Complaint.batch_id, isouter=True)
    )
    if product_id:
        query = query.filter(ProductionBatch.product_id == product_id)

    batches = (
        query.group_by(
            ProductionBatch.id, ProductionBatch.batch_id, ProductionBatch.lot_number,
            ProductionBatch.production_date, ProductionBatch.quantity_produced,
            ProductionBatch.status, Product.name,
        )
        .order_by(desc("complaint_count"))
        .limit(50)
        .all()
    )

    return {
        "batches": [
            {
                "batch_id": b.batch_id,
                "lot_number": b.lot_number,
                "production_date": b.production_date,
                "quantity_produced": b.quantity_produced,
                "status": b.status,
                "product_name": b.product_name,
                "complaint_count": b.complaint_count or 0,
                "severity_score": float(b.severity_score or 0),
                "risk_level": "high" if (b.complaint_count or 0) >= 3 else "medium" if (b.complaint_count or 0) >= 1 else "low",
            }
            for b in batches
        ]
    }


@router.get("/risk-assessment/matrix")
def get_risk_matrix(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """5×5 risk matrix: likelihood (complaint frequency bucket) vs severity."""
    # Get per-product complaint count and max severity
    product_data = (
        db.query(
            Product.name,
            func.count(Complaint.id).label("complaint_count"),
            func.max(_severity_case).label("max_severity"),
        )
        .join(Complaint, Product.id == Complaint.product_id)
        .group_by(Product.name)
        .all()
    )

    # Determine likelihood buckets
    max_cnt = max((r.complaint_count for r in product_data), default=1) or 1

    matrix = {}  # (likelihood, severity) -> list of products
    for r in product_data:
        ratio = r.complaint_count / max_cnt
        if ratio >= 0.8:
            likelihood = 5
        elif ratio >= 0.6:
            likelihood = 4
        elif ratio >= 0.4:
            likelihood = 3
        elif ratio >= 0.2:
            likelihood = 2
        else:
            likelihood = 1

        sev = int(r.max_severity or 1)
        sev = min(max(sev, 1), 4)  # clamp to 1-4
        key = f"{likelihood}_{sev}"
        if key not in matrix:
            matrix[key] = []
        matrix[key].append({"product": r.name, "complaint_count": r.complaint_count})

    cells = []
    for likelihood in range(1, 6):
        for severity in range(1, 5):
            key = f"{likelihood}_{severity}"
            items = matrix.get(key, [])
            risk_value = likelihood * severity
            cells.append({
                "likelihood": likelihood,
                "severity": severity,
                "risk_value": risk_value,
                "risk_level": "critical" if risk_value >= 12 else "high" if risk_value >= 8 else "medium" if risk_value >= 4 else "low",
                "products": items,
                "count": len(items),
            })

    return {
        "matrix": cells,
        "severity_labels": ["low", "medium", "high", "critical"],
        "likelihood_labels": ["rare", "unlikely", "possible", "likely", "almost_certain"],
    }


@router.get("/risk-assessment/kpis")
def get_risk_kpis(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    total_products = db.query(func.count(Product.id)).scalar() or 0
    products_with_complaints = (
        db.query(func.count(distinct(Complaint.product_id)))
        .filter(Complaint.product_id.isnot(None))
        .scalar() or 0
    )

    high_risk_count = (
        db.query(func.count(distinct(Complaint.product_id)))
        .filter(Complaint.reported_severity.in_(["critical", "high"]))
        .scalar() or 0
    )

    open_critical = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.reported_severity.in_(["critical", "high"]),
            Complaint.status.notin_(["resolved", "rejected", "closed"]),
        )
        .scalar() or 0
    )

    batches_affected = (
        db.query(func.count(distinct(Complaint.batch_id)))
        .filter(Complaint.batch_id.isnot(None))
        .scalar() or 0
    )

    return {
        "total_products": total_products,
        "products_with_complaints": products_with_complaints,
        "high_risk_products": high_risk_count,
        "open_critical_complaints": open_critical,
        "batches_affected": batches_affected,
    }


@router.get("/risk-assessment/alerts")
def get_risk_alerts(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Early warning alerts based on recent complaint spikes and severity."""
    alerts = []

    # 1. Products with recent critical/high complaints (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_critical = (
        db.query(
            Product.name,
            Product.product_id,
            func.count(Complaint.id).label("count"),
        )
        .join(Complaint, Product.id == Complaint.product_id)
        .filter(
            Complaint.submitted_date >= thirty_days_ago,
            Complaint.reported_severity.in_(["critical", "high"]),
        )
        .group_by(Product.name, Product.product_id)
        .having(func.count(Complaint.id) >= 2)
        .all()
    )
    for r in recent_critical:
        alerts.append({
            "type": "critical_spike",
            "severity": "critical",
            "message": f"{r.name} has {r.count} critical/high complaints in the last 30 days",
            "product_id": r.product_id,
            "product_name": r.name,
            "count": r.count,
        })

    # 2. Unresolved complaints older than 14 days
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    stale_count = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.status.notin_(["resolved", "rejected", "closed"]),
            Complaint.submitted_date <= fourteen_days_ago,
        )
        .scalar() or 0
    )
    if stale_count > 0:
        alerts.append({
            "type": "stale_complaints",
            "severity": "warning",
            "message": f"{stale_count} complaints unresolved for over 14 days",
            "count": stale_count,
        })

    # 3. Overdue CAPAs
    overdue_capa_count = (
        db.query(func.count(CorrectiveAction.id))
        .filter(
            CorrectiveAction.deadline < datetime.utcnow(),
            CorrectiveAction.status.notin_(["completed", "verified", "closed"]),
        )
        .scalar() or 0
    )
    if overdue_capa_count > 0:
        alerts.append({
            "type": "overdue_capa",
            "severity": "high",
            "message": f"{overdue_capa_count} CAPA actions are past their deadline",
            "count": overdue_capa_count,
        })

    # 4. Recurring category spikes (same category > 5 in last 60 days)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    category_spikes = (
        db.query(Complaint.category, func.count(Complaint.id).label("count"))
        .filter(
            Complaint.submitted_date >= sixty_days_ago,
            Complaint.category.isnot(None),
        )
        .group_by(Complaint.category)
        .having(func.count(Complaint.id) >= 5)
        .all()
    )
    for r in category_spikes:
        alerts.append({
            "type": "category_spike",
            "severity": "warning",
            "message": f"'{r.category}' category has {r.count} complaints in the last 60 days",
            "category": r.category,
            "count": r.count,
        })

    return {"alerts": alerts, "total": len(alerts)}


# =========================================================================
# 16-19. PREDICTIONS — Connected to XGBoost Model
# =========================================================================

@router.get("/predictions/status")
def get_prediction_status(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    total_predictions = db.query(func.count(ModelPrediction.id)).scalar() or 0
    latest = db.query(ModelPrediction).order_by(ModelPrediction.created_at.desc()).first()
    model_ready = is_model_available()

    return {
        "model_available": model_ready,
        "model_version": MODEL_VERSION if model_ready else None,
        "model_error": get_model_error() if not model_ready else None,
        "total_predictions": total_predictions,
        "latest_prediction": {
            "prediction_id": latest.prediction_id,
            "model_version": latest.model_version,
            "created_at": latest.created_at,
        } if latest else None,
        "status": "active" if model_ready else "no_model",
    }


@router.post("/predictions/predict")
def run_prediction(
    data: PredictionInput,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Resolve product name from product_id if provided
    product_name = None
    product_category = None
    facility_name = data.facility
    batch_code = data.batch_id

    if data.product_id:
        product = db.query(Product).filter(Product.id == data.product_id).first()
        if product:
            product_name = product.name
            product_category = product.category

    # Generate prediction ID
    year = datetime.utcnow().year
    pred_count = db.query(func.count(ModelPrediction.id)).scalar() or 0
    pred_id = f"PRED-{year}-{(pred_count + 1):04d}"

    input_features = {
        "product_id": data.product_id,
        "product_name": product_name,
        "product_category": product_category,
        "category": data.category,
        "severity": data.severity,
        "description": data.description,
        "batch_id": data.batch_id,
        "facility": data.facility,
        "title": data.title,
    }

    # Run XGBoost prediction
    if is_model_available():
        ml_result = predict_complaint_risk(
            product_name=product_name,
            product_category=product_category,
            complaint_category=data.category,
            severity=data.severity,
            description=data.description,
            facility=facility_name,
            batch_id=batch_code,
            title=data.title or (data.description[:100] if data.description else None),
        )

        prediction_result = {
            "risk_class": ml_result.get("risk_class"),
            "risk_label": ml_result.get("risk_label"),
            "risk_probability": ml_result.get("risk_probability"),
            "predicted_severity": ml_result.get("predicted_severity"),
            "predicted_category": ml_result.get("predicted_category"),
            "confidence": ml_result.get("confidence"),
            "model_version": ml_result.get("model_version"),
            "feature_summary": ml_result.get("feature_summary"),
        }
        confidence_str = str(ml_result.get("confidence", 0.0))
        status_msg = "success"
    else:
        prediction_result = {
            "predicted_severity": data.severity or "medium",
            "predicted_category": data.category or "quality_defect",
            "confidence": 0.0,
            "note": "Model not available — " + (get_model_error() or "unknown error"),
        }
        confidence_str = "0.0"
        status_msg = "Model Unavailable"

    prediction = ModelPrediction(
        prediction_id=pred_id,
        model_version=MODEL_VERSION if is_model_available() else "unavailable",
        input_features=input_features,
        prediction_result=prediction_result,
        confidence_score=confidence_str,
        created_by=current_user.id,
    )
    db.add(prediction)

    _create_audit_log(db, current_user, "run_prediction", "prediction", pred_id, input_features)
    db.commit()

    return {
        "status": status_msg,
        "prediction_id": pred_id,
        "prediction": prediction_result,
    }


@router.get("/predictions/history")
def get_prediction_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total = db.query(func.count(ModelPrediction.id)).scalar() or 0
    predictions = (
        db.query(ModelPrediction)
        .order_by(ModelPrediction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [
            {
                "id": p.id,
                "prediction_id": p.prediction_id,
                "model_version": p.model_version,
                "input_features": p.input_features,
                "prediction_result": p.prediction_result,
                "confidence_score": p.confidence_score,
                "created_at": p.created_at,
            }
            for p in predictions
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/predictions/model-info")
def get_model_info(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    total = db.query(func.count(ModelPrediction.id)).scalar() or 0
    latest = db.query(ModelPrediction).order_by(ModelPrediction.created_at.desc()).first()

    versions = (
        db.query(ModelPrediction.model_version, func.count(ModelPrediction.id).label("count"))
        .group_by(ModelPrediction.model_version)
        .all()
    )

    # Get real model metadata
    metadata = get_model_metadata()
    feature_imp = get_feature_importance(top_n=15)

    return {
        "model_deployed": metadata.get("available", False),
        "model_metadata": metadata,
        "feature_importance": feature_imp,
        "total_predictions": total,
        "current_version": MODEL_VERSION if metadata.get("available") else None,
        "last_prediction_at": latest.created_at if latest else None,
        "versions": [{"version": v.model_version, "prediction_count": v.count} for v in versions],
        "metrics": {
            "best_auc": metadata.get("training_metrics", {}).get("best_auc"),
            "best_iteration": metadata.get("training_metrics", {}).get("best_iteration"),
            "algorithm": metadata.get("algorithm"),
            "n_features": metadata.get("n_features"),
            "n_estimators": metadata.get("n_estimators"),
        } if metadata.get("available") else {
            "note": "Model not loaded. " + (get_model_error() or ""),
        },
    }


# =========================================================================
# 20-26. CAPA
# =========================================================================

@router.get("/capa/analytics")
def get_capa_analytics(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """CAPA analytics charts data."""
    # By status
    by_status = (
        db.query(CorrectiveAction.status, func.count(CorrectiveAction.id).label("count"))
        .group_by(CorrectiveAction.status)
        .all()
    )
    # By type
    by_type = (
        db.query(CorrectiveAction.action_type, func.count(CorrectiveAction.id).label("count"))
        .group_by(CorrectiveAction.action_type)
        .all()
    )
    # By priority
    by_priority = (
        db.query(CorrectiveAction.priority, func.count(CorrectiveAction.id).label("count"))
        .group_by(CorrectiveAction.priority)
        .all()
    )
    # By effectiveness
    by_effectiveness = (
        db.query(CorrectiveAction.effectiveness_status, func.count(CorrectiveAction.id).label("count"))
        .filter(CorrectiveAction.effectiveness_status.isnot(None))
        .group_by(CorrectiveAction.effectiveness_status)
        .all()
    )
    # Monthly trend
    monthly = (
        db.query(
            extract("year", CorrectiveAction.created_at).label("year"),
            extract("month", CorrectiveAction.created_at).label("month"),
            func.count(CorrectiveAction.id).label("count"),
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    total = db.query(func.count(CorrectiveAction.id)).scalar() or 0
    completed = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.status.in_(["completed", "verified", "closed"])
    ).scalar() or 0
    overdue = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.deadline < datetime.utcnow(),
        CorrectiveAction.status.notin_(["completed", "verified", "closed"]),
    ).scalar() or 0

    return {
        "kpis": {
            "total": total,
            "completed": completed,
            "completion_rate": round((completed / max(total, 1)) * 100, 1),
            "overdue": overdue,
        },
        "by_status": [{"status": r.status, "count": r.count} for r in by_status],
        "by_type": [{"type": r.action_type, "count": r.count} for r in by_type],
        "by_priority": [{"priority": r.priority, "count": r.count} for r in by_priority],
        "by_effectiveness": [{"effectiveness": r.effectiveness_status, "count": r.count} for r in by_effectiveness],
        "monthly_trend": [
            {"year": int(r.year), "month": int(r.month), "count": r.count}
            for r in monthly if r.year and r.month
        ],
    }


@router.get("/capa/overdue")
def get_overdue_capas(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CorrectiveAction).filter(
        CorrectiveAction.deadline < datetime.utcnow(),
        CorrectiveAction.status.notin_(["completed", "verified", "closed"]),
    )

    total = query.count()
    items = query.order_by(CorrectiveAction.deadline.asc()).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": c.id,
                "capa_id": c.capa_id,
                "action_type": c.action_type,
                "title": c.title,
                "priority": c.priority,
                "status": c.status,
                "assigned_to": c.assigned_to,
                "deadline": c.deadline,
                "days_overdue": (datetime.utcnow() - c.deadline).days if c.deadline else 0,
                "created_at": c.created_at,
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/capa/effectiveness")
def get_capa_effectiveness(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Effectiveness monitoring data."""
    total = db.query(func.count(CorrectiveAction.id)).scalar() or 0

    effective = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.effectiveness_status == "effective"
    ).scalar() or 0
    not_effective = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.effectiveness_status == "not_effective"
    ).scalar() or 0
    pending_review = db.query(func.count(CorrectiveAction.id)).filter(
        or_(
            CorrectiveAction.effectiveness_status.is_(None),
            CorrectiveAction.effectiveness_status == "pending_review",
        )
    ).scalar() or 0

    # Per-type effectiveness
    by_type = (
        db.query(
            CorrectiveAction.action_type,
            CorrectiveAction.effectiveness_status,
            func.count(CorrectiveAction.id).label("count"),
        )
        .group_by(CorrectiveAction.action_type, CorrectiveAction.effectiveness_status)
        .all()
    )

    # Recently verified
    recently_verified = (
        db.query(CorrectiveAction)
        .filter(CorrectiveAction.verified_at.isnot(None))
        .order_by(CorrectiveAction.verified_at.desc())
        .limit(10)
        .all()
    )

    return {
        "summary": {
            "total": total,
            "effective": effective,
            "not_effective": not_effective,
            "pending_review": pending_review,
            "effectiveness_rate": round((effective / max(total, 1)) * 100, 1),
        },
        "by_type": [
            {"type": r.action_type, "effectiveness": r.effectiveness_status, "count": r.count}
            for r in by_type
        ],
        "recently_verified": [
            {
                "capa_id": c.capa_id,
                "title": c.title,
                "action_type": c.action_type,
                "effectiveness_status": c.effectiveness_status,
                "verified_at": c.verified_at,
                "effectiveness_evidence": c.effectiveness_evidence,
            }
            for c in recently_verified
        ],
    }


@router.get("/capa")
def list_capa(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    effectiveness_status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|deadline|status|priority)$"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CorrectiveAction)

    if status:
        query = query.filter(CorrectiveAction.status == status)
    if action_type:
        query = query.filter(CorrectiveAction.action_type == action_type)
    if priority:
        query = query.filter(CorrectiveAction.priority == priority)
    if assigned_to:
        query = query.filter(CorrectiveAction.assigned_to.ilike(f"%{assigned_to}%"))
    if effectiveness_status:
        query = query.filter(CorrectiveAction.effectiveness_status == effectiveness_status)
    if search:
        query = query.filter(
            or_(
                CorrectiveAction.capa_id.ilike(f"%{search}%"),
                CorrectiveAction.title.ilike(f"%{search}%"),
                CorrectiveAction.description.ilike(f"%{search}%"),
            )
        )

    total = query.count()

    sort_col = getattr(CorrectiveAction, sort_by, CorrectiveAction.created_at)
    order_func = desc if sort_order == "desc" else asc
    items = query.order_by(order_func(sort_col)).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": c.id,
                "capa_id": c.capa_id,
                "action_type": c.action_type,
                "title": c.title,
                "description": c.description,
                "priority": c.priority,
                "status": c.status,
                "assigned_to": c.assigned_to,
                "deadline": c.deadline,
                "effectiveness_status": c.effectiveness_status,
                "created_at": c.created_at,
                "completed_at": c.completed_at,
                "complaint_id": c.complaint_id,
                "investigation_id": c.investigation_id,
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/capa/{capa_id}")
def get_capa_detail(
    capa_id: str,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    capa = (
        db.query(CorrectiveAction)
        .options(joinedload(CorrectiveAction.complaint), joinedload(CorrectiveAction.investigation))
        .filter(CorrectiveAction.capa_id == capa_id)
        .first()
    )
    if not capa:
        raise HTTPException(status_code=404, detail="CAPA not found")

    # Build timeline
    timeline = [{"event": "Created", "date": capa.created_at, "detail": f"CAPA {capa.capa_id} created"}]
    if capa.completed_at:
        timeline.append({"event": "Completed", "date": capa.completed_at, "detail": "Action completed"})
    if capa.verified_at:
        timeline.append({"event": "Verified", "date": capa.verified_at, "detail": f"Effectiveness: {capa.effectiveness_status}"})
    timeline.sort(key=lambda x: x["date"] or datetime.min)

    return {
        "id": capa.id,
        "capa_id": capa.capa_id,
        "action_type": capa.action_type,
        "title": capa.title,
        "description": capa.description,
        "priority": capa.priority,
        "status": capa.status,
        "assigned_to": capa.assigned_to,
        "deadline": capa.deadline,
        "completion_evidence": capa.completion_evidence,
        "effectiveness_status": capa.effectiveness_status,
        "effectiveness_evidence": capa.effectiveness_evidence,
        "created_at": capa.created_at,
        "completed_at": capa.completed_at,
        "verified_at": capa.verified_at,
        "record_type": capa.record_type,
        "complaint": _complaint_summary(capa.complaint) if capa.complaint else None,
        "investigation": {
            "id": capa.investigation.id,
            "investigation_id": capa.investigation.investigation_id,
            "title": capa.investigation.title,
            "root_cause_category": capa.investigation.root_cause_category,
            "status": capa.investigation.status,
        } if capa.investigation else None,
        "timeline": timeline,
    }


@router.post("/capa")
def create_capa(
    capa_data: CAPACreate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    year = datetime.utcnow().year
    count = db.query(func.count(CorrectiveAction.id)).scalar() or 0
    capa_id = f"CAPA-{year}-{(count + 1):04d}"

    capa = CorrectiveAction(
        capa_id=capa_id,
        action_type=capa_data.action_type,
        title=capa_data.title,
        description=capa_data.description or "",
        priority=capa_data.priority,
        assigned_to=capa_data.assigned_to or "",
        complaint_id=capa_data.complaint_id,
        investigation_id=capa_data.investigation_id,
        deadline=capa_data.deadline,
        record_type="admin_created",
    )
    db.add(capa)

    _create_audit_log(db, current_user, "create_capa", "capa", capa_id, {
        "title": capa_data.title,
        "action_type": capa_data.action_type,
        "priority": capa_data.priority,
    })

    db.commit()
    return {"capa_id": capa_id, "message": "CAPA created successfully"}


@router.put("/capa/{capa_id}")
def update_capa(
    capa_id: str,
    update_data: CAPAUpdate,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    capa = db.query(CorrectiveAction).filter(CorrectiveAction.capa_id == capa_id).first()
    if not capa:
        raise HTTPException(status_code=404, detail="CAPA not found")

    changes: dict = {}

    if update_data.status is not None:
        changes["status"] = {"old": capa.status, "new": update_data.status}
        capa.status = update_data.status
        if update_data.status in ("completed", "verified", "closed"):
            capa.completed_at = capa.completed_at or datetime.utcnow()
    if update_data.assigned_to is not None:
        changes["assigned_to"] = {"old": capa.assigned_to, "new": update_data.assigned_to}
        capa.assigned_to = update_data.assigned_to
    if update_data.priority is not None:
        changes["priority"] = {"old": capa.priority, "new": update_data.priority}
        capa.priority = update_data.priority
    if update_data.completion_evidence is not None:
        capa.completion_evidence = update_data.completion_evidence
    if update_data.effectiveness_status is not None:
        capa.effectiveness_status = update_data.effectiveness_status
        if update_data.effectiveness_status in ("effective", "not_effective"):
            capa.verified_at = capa.verified_at or datetime.utcnow()
    if update_data.effectiveness_evidence is not None:
        capa.effectiveness_evidence = update_data.effectiveness_evidence
    if update_data.deadline is not None:
        capa.deadline = update_data.deadline

    _create_audit_log(db, current_user, "update_capa", "capa", capa_id, changes)

    db.commit()
    return {"message": "CAPA updated successfully", "capa_id": capa_id}


# =========================================================================
# 27-30. FILTER DROPDOWNS
# =========================================================================

@router.get("/filters/products")
def get_filter_products(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.name).all()
    return [{"id": p.id, "product_id": p.product_id, "name": p.name, "category": p.category} for p in products]


@router.get("/filters/facilities")
def get_filter_facilities(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    facilities = db.query(Facility).order_by(Facility.name).all()
    return [{"id": f.id, "facility_id": f.facility_id, "name": f.name, "location": f.location} for f in facilities]


@router.get("/filters/categories")
def get_filter_categories(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    categories = (
        db.query(distinct(Complaint.category))
        .filter(Complaint.category.isnot(None))
        .order_by(Complaint.category)
        .all()
    )
    return [c[0] for c in categories]


@router.get("/filters/customers")
def get_filter_customers(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    customers = (
        db.query(distinct(Complaint.customer_name))
        .filter(Complaint.customer_name.isnot(None))
        .order_by(Complaint.customer_name)
        .all()
    )
    return [c[0] for c in customers]
