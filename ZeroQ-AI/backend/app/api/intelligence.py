"""
Issue-intelligence API: AI analysis, admin verification & resolution,
learning controls, impact analytics and the real-time WebSocket channel.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.core.security import decode_token
from app.database.connection import get_db
from app.intelligence import llm
from app.intelligence.engine import analyze_text_preview, run_analysis
from app.intelligence.impact import assumptions, compute_kpis, compute_trends
from app.intelligence.learning import NotEnoughVerifiedData, learning_status, retrain
from app.intelligence.realtime import broker, complaint_event_payload
from app.intelligence.retrieval import get_index, invalidate_index
from app.intelligence.taxonomy import CATEGORIES, SUBCATEGORY_TO_CATEGORY
from app.models.complaint import Complaint, ComplaintStatusHistory
from app.models.intelligence import IncidentResolution, IssueAnalysis
from app.models.notification import AuditLog, Notification
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter()

WS_AUTH_TIMEOUT_SECONDS = 10
MAX_PREVIEW_CHARS = 4000


# ── serialisation ─────────────────────────────────────────────────────────

def serialize_analysis(a: Optional[IssueAnalysis], audience: str = "admin") -> Optional[dict]:
    if a is None:
        return None
    base = {
        "status": a.status,
        "original_text": a.original_text,
        "detected_language": a.detected_language,
        "language_name": a.language_name,
        "is_code_mixed": a.is_code_mixed,
        "english_text": a.english_text,
        "translation_method": a.translation_method,
        "symptoms": [s.get("symptom") for s in (a.symptoms or [])],
        "prediction_source": a.prediction_source,
        "predicted_category": a.predicted_category,
        "predicted_subcategory": a.predicted_subcategory,
        "predicted_severity": a.predicted_severity,
        "affected_product": a.affected_product,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if audience == "customer":
        return base  # unverified root causes / internal evidence stay admin-only
    return base | {
        "id": a.id,
        "symptom_details": a.symptoms or [],
        "entities": a.entities or {},
        "predicted_root_cause": a.predicted_root_cause,
        "recommended_resolution": a.recommended_resolution,
        "confidence": a.confidence,
        "confidence_threshold": settings.ML_CONFIDENCE_THRESHOLD,
        "is_low_confidence": a.is_low_confidence,
        "fallback_reason": a.fallback_reason,
        "ml_result": a.ml_result,
        "llm_result": a.llm_result,
        "batch_risk": a.batch_risk,
        "similar_incidents": a.similar_incidents or [],
        "root_cause_distribution": a.root_cause_distribution or [],
        "resolution_options": a.resolution_options or [],
        "model_version": a.model_version,
        "error": a.error,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def serialize_resolution(r: Optional[IncidentResolution], audience: str = "admin") -> Optional[dict]:
    if r is None:
        return None
    base = {
        "verified_category": r.verified_category,
        "verified_subcategory": r.verified_subcategory,
        "confirmed_root_cause": r.confirmed_root_cause,
        "resolution_action": r.resolution_action,
        "admin_explanation": r.admin_explanation,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
    }
    if audience == "customer":
        return base
    return base | {
        "id": r.id, "predicted_category": r.predicted_category, "prediction_source": r.prediction_source,
        "category_correct": r.category_correct, "root_cause_correct": r.root_cause_correct,
        "corrected_fields": r.corrected_fields or [], "units_contained": r.units_contained,
        "units_at_risk": r.units_at_risk,
        "downtime_avoided_hours": r.downtime_avoided_hours, "resolved_by": r.resolved_by,
        "used_in_training_run": r.used_in_training_run,
    }


# ── background analysis (called from complaint submission) ────────────────

def analyze_complaint_job(bind, complaint_pk: int) -> None:
    """Runs after the submit response is sent; uses its own session on the same engine."""
    db = Session(bind=bind)
    try:
        complaint = db.get(Complaint, complaint_pk)
        if complaint is None:
            return
        try:
            analysis = run_analysis(db, complaint)
            extra = {"prediction_source": analysis.prediction_source,
                     "predicted_category": analysis.predicted_category,
                     "confidence": analysis.confidence, "language": analysis.language_name}
        except Exception as exc:
            db.rollback()
            logger.exception("Issue analysis failed for complaint %s", complaint_pk)
            _store_failed_analysis(db, complaint, exc)
            extra = {"prediction_source": "none", "error": "analysis_failed"}
        broker.publish("analysis.completed", complaint_event_payload(complaint, extra),
                       user_ids=[complaint.submitted_by_user_id], to_admins=True)
    finally:
        db.close()


def _store_failed_analysis(db: Session, complaint: Complaint, exc: Exception) -> None:
    existing = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == complaint.id).first()
    row = existing or IssueAnalysis(complaint_id=complaint.id, original_text=complaint.description or "")
    row.status, row.prediction_source, row.error = "failed", "none", type(exc).__name__
    db.add(row)
    db.commit()


RECOVERY_BATCH_LIMIT = 200


def recover_missing_analyses(bind) -> int:
    """Re-run analysis for live complaints that have none (e.g. the process stopped before the
    background job ran). Failed analyses are left for an admin to re-run, to avoid retry loops.
    Returns how many complaints were analysed."""
    db = Session(bind=bind)
    try:
        missing = (db.query(Complaint.id)
                   .outerjoin(IssueAnalysis, IssueAnalysis.complaint_id == Complaint.id)
                   .filter(IssueAnalysis.id.is_(None), Complaint.submitted_by_user_id.isnot(None),
                           Complaint.customer_id.is_(None))   # live submissions, not the imported dataset
                   .order_by(Complaint.id.desc()).limit(RECOVERY_BATCH_LIMIT).all())
    finally:
        db.close()
    for (pk,) in missing:
        analyze_complaint_job(bind, pk)
    if missing:
        logger.info("Recovered %d complaint analyses", len(missing))
    return len(missing)


# ── admin: analysis & verification ────────────────────────────────────────

def _get_complaint(db: Session, complaint_id: str) -> Complaint:
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.get("/config")
def get_config(current_user=Depends(get_current_admin)):
    return {
        "llm_available": llm.is_llm_available(),
        "llm_configured": llm.is_configured(),
        "llm_model": settings.LLM_MODEL if llm.is_configured() else None,
        "ml_confidence_threshold": settings.ML_CONFIDENCE_THRESHOLD,
        "min_historical_similarity": settings.MIN_HISTORICAL_SIMILARITY,
        "categories": CATEGORIES,
        "subcategories": SUBCATEGORY_TO_CATEGORY,
        "assumptions": assumptions(),
    }


LLM_USAGE_WINDOW_DAYS = 30


@router.get("/llm/status")
def get_llm_status(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Operational view of the LLM fallback. Never returns credentials."""
    since = datetime.utcnow() - timedelta(days=LLM_USAGE_WINDOW_DAYS)
    rows = db.query(IssueAnalysis.llm_result).filter(
        IssueAnalysis.llm_result.isnot(None), IssueAnalysis.created_at >= since).all()
    totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
    by_op: dict = {}
    for (res,) in rows:
        for u in (res or {}).get("usage", []):
            totals["calls"] += 1
            totals["input_tokens"] += u.get("input_tokens", 0)
            totals["output_tokens"] += u.get("output_tokens", 0)
            totals["estimated_cost_usd"] += u.get("estimated_cost_usd", 0.0)
            op = by_op.setdefault(u.get("operation", "unknown"), {"calls": 0, "latency_ms_total": 0})
            op["calls"] += 1
            op["latency_ms_total"] += u.get("latency_ms", 0)
    for op in by_op.values():
        op["avg_latency_ms"] = round(op.pop("latency_ms_total") / op["calls"]) if op["calls"] else None
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 4)
    return {
        "configured": llm.is_configured(),
        "enabled": settings.LLM_ENABLED,
        "model": settings.LLM_MODEL,
        "circuit": llm.circuit_status(),
        "usage_window_days": LLM_USAGE_WINDOW_DAYS,
        "usage": totals,
        "by_operation": by_op,
        "pricing_note": (f"Cost is an estimate at list price ${settings.LLM_INPUT_PRICE_PER_MTOK}/"
                         f"${settings.LLM_OUTPUT_PRICE_PER_MTOK} per million input/output tokens."),
        "setup_required": None if llm.is_configured() else
        "Set ANTHROPIC_API_KEY in the backend environment (and keep LLM_ENABLED=true) to enable the LLM fallback.",
    }


@router.get("/incidents/{complaint_id}")
def get_incident(complaint_id: str, current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    complaint = _get_complaint(db, complaint_id)
    analysis = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == complaint.id).first()
    resolution = db.query(IncidentResolution).filter(IncidentResolution.complaint_id == complaint.id).first()
    return {
        "complaint_id": complaint.complaint_id,
        "status": complaint.status,
        "record_type": complaint.record_type,
        "title": complaint.title,
        "description": complaint.description,
        "category": complaint.category,
        "reported_severity": complaint.reported_severity,
        "product": complaint.product.name if complaint.product else None,
        "version": complaint.last_updated.isoformat() if complaint.last_updated else None,
        "analysis": serialize_analysis(analysis),
        "resolution": serialize_resolution(resolution),
    }


@router.post("/incidents/{complaint_id}/analyze")
def analyze_incident(complaint_id: str, current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    complaint = _get_complaint(db, complaint_id)
    analysis = run_analysis(db, complaint)
    broker.publish("analysis.completed", complaint_event_payload(complaint, {
        "prediction_source": analysis.prediction_source, "predicted_category": analysis.predicted_category}),
        to_admins=True)
    return serialize_analysis(analysis)


class ResolveRequest(BaseModel):
    verified_category: str = Field(min_length=2, max_length=120)
    verified_subcategory: Optional[str] = Field(default=None, max_length=120)
    confirmed_root_cause: str = Field(min_length=3, max_length=2000)
    resolution_action: str = Field(min_length=3, max_length=2000)
    admin_explanation: str = Field(min_length=10, max_length=4000)
    units_contained: int = Field(default=0, ge=0, le=10_000_000)
    # Units of the affected batch/lot that were at risk; required for a wastage-reduction %.
    units_at_risk: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    downtime_avoided_hours: float = Field(default=0.0, ge=0.0, le=10_000)
    # Optimistic concurrency: the complaint `version` the admin was looking at. If the complaint
    # changed since (another admin, a status update), the resolve is rejected with 409.
    expected_version: Optional[str] = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _contained_within_at_risk(self):
        if self.units_at_risk is not None and self.units_contained > self.units_at_risk:
            raise ValueError("units_contained cannot exceed units_at_risk")
        return self

    @field_validator("verified_category", "verified_subcategory", "confirmed_root_cause",
                     "resolution_action", "admin_explanation")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


@router.post("/incidents/{complaint_id}/resolve")
def resolve_incident(complaint_id: str, body: ResolveRequest, current_user=Depends(get_current_admin),
                     db: Session = Depends(get_db)):
    # Row lock on databases that support it (PostgreSQL); the unique constraint on
    # incident_resolutions.complaint_id is the guard everywhere (incl. SQLite).
    complaint = (db.query(Complaint).filter(Complaint.complaint_id == complaint_id)
                 .with_for_update().first())
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if db.query(IncidentResolution).filter(IncidentResolution.complaint_id == complaint.id).first():
        raise HTTPException(status_code=409, detail="Incident already resolved")
    current_version = complaint.last_updated.isoformat() if complaint.last_updated else None
    if body.expected_version and body.expected_version != current_version:
        raise HTTPException(status_code=409, detail="This incident changed since you opened it. Reload and review.")
    analysis = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == complaint.id).first()

    corrected = []
    cat_ok = rc_ok = None
    if analysis and analysis.status == "completed":
        cat_ok = _norm(analysis.predicted_category) == _norm(body.verified_category)
        rc_ok = _norm(analysis.predicted_root_cause) == _norm(body.confirmed_root_cause)
        if not cat_ok:
            corrected.append("category")
        if body.verified_subcategory and _norm(analysis.predicted_subcategory) != _norm(body.verified_subcategory):
            corrected.append("subcategory")
        if not rc_ok:
            corrected.append("root_cause")

    now = datetime.utcnow()
    resolution = IncidentResolution(
        complaint_id=complaint.id, analysis_id=analysis.id if analysis else None,
        original_text=analysis.original_text if analysis else complaint.description,
        detected_language=analysis.detected_language if analysis else None,
        english_text=analysis.english_text if analysis else complaint.description,
        predicted_category=analysis.predicted_category if analysis else None,
        predicted_subcategory=analysis.predicted_subcategory if analysis else None,
        prediction_source=analysis.prediction_source if analysis else None,
        verified_category=body.verified_category, verified_subcategory=body.verified_subcategory,
        confirmed_root_cause=body.confirmed_root_cause, resolution_action=body.resolution_action,
        admin_explanation=body.admin_explanation, category_correct=cat_ok, root_cause_correct=rc_ok,
        corrected_fields=corrected, units_contained=body.units_contained, units_at_risk=body.units_at_risk,
        downtime_avoided_hours=body.downtime_avoided_hours, resolved_by=current_user.email, resolved_at=now,
    )
    old_status = complaint.status
    complaint.status = "resolved"
    complaint.resolved_date = now
    complaint.last_updated = now
    complaint.category = body.verified_category
    if body.verified_subcategory:
        complaint.complaint_subcategory = body.verified_subcategory
    complaint.customer_visible_update = body.admin_explanation
    db.add(resolution)
    db.add(ComplaintStatusHistory(
        complaint_id=complaint.id, old_status=old_status, new_status="resolved",
        changed_by=current_user.email, changed_by_role=current_user.role,
        notes=f"Resolved. Root cause: {body.confirmed_root_cause}. Action: {body.resolution_action}",
        is_customer_visible=True, changed_at=now))
    db.add(AuditLog(user_id=current_user.id, action="resolve_incident", resource_type="complaint",
                    resource_id=complaint.complaint_id,
                    details={"verified_category": body.verified_category, "corrected_fields": corrected}))
    if complaint.submitted_by_user_id:
        db.add(Notification(user_id=complaint.submitted_by_user_id, title=f"{complaint.complaint_id} resolved",
                            message=body.admin_explanation[:500], notification_type="resolution"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Incident already resolved")
    db.refresh(complaint)
    db.refresh(resolution)
    invalidate_index()
    broker.publish("complaint.resolved", complaint_event_payload(complaint, {
        "resolution": serialize_resolution(resolution, audience="customer")}),
        user_ids=[complaint.submitted_by_user_id], to_admins=True)
    return {"complaint_id": complaint.complaint_id, "status": complaint.status,
            "version": complaint.last_updated.isoformat(), "resolution": serialize_resolution(resolution)}


class PreviewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=MAX_PREVIEW_CHARS)


@router.post("/preview")
def preview(body: PreviewRequest, current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    return analyze_text_preview(db, body.text.strip())


# ── analytics ─────────────────────────────────────────────────────────────

def _parse_date(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date: {value}")
    return d.replace(hour=23, minute=59, second=59) if end_of_day and len(value) <= 10 else d


SCOPE_PATTERN = "^(live|imported|all)$"


@router.get("/kpis")
def kpis(start: Optional[str] = Query(None), end: Optional[str] = Query(None),
         category: Optional[str] = Query(None, max_length=120),
         scope: str = Query("live", pattern=SCOPE_PATTERN),
         current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    return compute_kpis(db, _parse_date(start), _parse_date(end, True), category or None, scope)


@router.get("/trends")
def trends(start: Optional[str] = Query(None), end: Optional[str] = Query(None),
           category: Optional[str] = Query(None, max_length=120),
           scope: str = Query("live", pattern=SCOPE_PATTERN),
           current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    return compute_trends(db, _parse_date(start), _parse_date(end, True), category or None, scope)


# ── learning ──────────────────────────────────────────────────────────────

@router.get("/learning/status")
def get_learning_status(current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    status = learning_status(db)
    status["historical_index"] = {"size": get_index(db).size, "backend": get_index(db).encoder.backend}
    return status


class RetrainRequest(BaseModel):
    force: bool = False


@router.post("/learning/retrain")
def post_retrain(body: RetrainRequest, current_user=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        run = retrain(db, trigger="manual", force=body.force, user=current_user.email)
    except NotEnoughVerifiedData as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    broker.publish("model.retrained", {"model_version": run.model_version, "promoted": run.promoted}, to_admins=True)
    metrics = {k: v for k, v in (run.metrics or {}).items() if k != "benchmark_items"}
    return {"id": run.id, "model_version": run.model_version, "status": run.status, "promoted": run.promoted,
            "notes": run.notes, "metrics": metrics, "previous_metrics": run.previous_metrics}


# ── WebSocket ─────────────────────────────────────────────────────────────

@ws_router.websocket("/api/ws")
async def events_socket(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        msg = await asyncio.wait_for(websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS)
    except WebSocketDisconnect:
        db.close()
        return  # client left before authenticating; the socket is already closed
    except (asyncio.TimeoutError, ValueError, KeyError):
        db.close()
        await websocket.close(code=4401)
        return
    payload = decode_token(msg.get("token", "")) if isinstance(msg, dict) and msg.get("type") == "auth" else None
    user = db.get(User, int(payload["sub"])) if payload and payload.get("sub") else None
    db.close()
    if user is None or not user.is_active:
        await websocket.close(code=4401)
        return
    broker.register(websocket, user.id, user.role)
    try:
        await websocket.send_json({"type": "connected", "user_id": user.id, "role": user.role})
        expires_at = float(payload.get("exp", 0)) or None
        while True:
            remaining = (expires_at - time.time()) if expires_at else None
            if remaining is not None and remaining <= 0:
                raise asyncio.TimeoutError
            message = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
            if message == "ping":
                await websocket.send_text("pong")
    except asyncio.TimeoutError:
        # Token expired: the client must re-authenticate (a fresh login issues a new token).
        await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unregister(websocket, user.id)
