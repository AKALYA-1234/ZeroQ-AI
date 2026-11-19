"""
Issue-intelligence tables: AI analysis per complaint, admin-verified resolutions
(the only data the learning loop trains on), customer satisfaction feedback and
classifier training runs.

All tables are new, so `Base.metadata.create_all` (run at startup and by
scripts/migrate_issue_intelligence.py) creates them without altering existing tables.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, JSON, Index,
    UniqueConstraint,
)
from app.database.base import Base


class IssueAnalysis(Base):
    __tablename__ = "issue_analyses"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, unique=True, index=True)

    # Language understanding — the original text is never overwritten.
    original_text = Column(Text, nullable=False)
    detected_language = Column(String(20), nullable=True, index=True)
    language_name = Column(String(80), nullable=True)
    is_code_mixed = Column(Boolean, default=False)
    english_text = Column(Text, nullable=True)
    translation_method = Column(String(30), nullable=True)  # none | llm | glossary | unavailable
    symptoms = Column(JSON, nullable=True)
    entities = Column(JSON, nullable=True)

    # Prediction
    prediction_source = Column(String(20), nullable=False, index=True)  # ml | llm | rules | none
    predicted_category = Column(String(120), nullable=True, index=True)
    predicted_subcategory = Column(String(120), nullable=True)
    predicted_root_cause = Column(Text, nullable=True)
    predicted_severity = Column(String(20), nullable=True)
    affected_product = Column(String(255), nullable=True)
    recommended_resolution = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    is_low_confidence = Column(Boolean, default=False, index=True)
    fallback_reason = Column(String(255), nullable=True)

    # Evidence
    ml_result = Column(JSON, nullable=True)
    llm_result = Column(JSON, nullable=True)
    batch_risk = Column(JSON, nullable=True)
    similar_incidents = Column(JSON, nullable=True)
    root_cause_distribution = Column(JSON, nullable=True)
    resolution_options = Column(JSON, nullable=True)
    model_version = Column(String(80), nullable=True)

    status = Column(String(20), default="completed")  # completed | failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IncidentResolution(Base):
    """Admin-verified ground truth. One row per complaint (unique) — prevents double resolution."""
    __tablename__ = "incident_resolutions"
    __table_args__ = (UniqueConstraint("complaint_id", name="uq_resolution_complaint"),)

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("issue_analyses.id"), nullable=True)

    original_text = Column(Text, nullable=True)
    detected_language = Column(String(20), nullable=True)
    english_text = Column(Text, nullable=True)

    predicted_category = Column(String(120), nullable=True)
    predicted_subcategory = Column(String(120), nullable=True)
    prediction_source = Column(String(20), nullable=True)
    verified_category = Column(String(120), nullable=False, index=True)
    verified_subcategory = Column(String(120), nullable=True)
    confirmed_root_cause = Column(Text, nullable=False)
    resolution_action = Column(Text, nullable=False)
    admin_explanation = Column(Text, nullable=False)
    category_correct = Column(Boolean, nullable=True)
    root_cause_correct = Column(Boolean, nullable=True)
    corrected_fields = Column(JSON, nullable=True)

    # Admin-entered impact figures (never inferred).
    units_contained = Column(Integer, default=0)
    downtime_avoided_hours = Column(Float, default=0.0)

    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime, default=datetime.utcnow, index=True)
    used_in_training_run = Column(Integer, ForeignKey("model_training_runs.id"), nullable=True)


class ResolutionFeedback(Base):
    __tablename__ = "resolution_feedback"
    __table_args__ = (UniqueConstraint("complaint_id", name="uq_feedback_complaint"),)

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1..5
    satisfied = Column(Boolean, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ModelTrainingRun(Base):
    __tablename__ = "model_training_runs"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(80), nullable=False)
    trigger = Column(String(30), default="manual")  # bootstrap | manual | scheduled
    status = Column(String(20), default="completed")  # completed | rejected | failed
    promoted = Column(Boolean, default=False)
    n_training_samples = Column(Integer, default=0)
    n_verified_samples = Column(Integer, default=0)
    metrics = Column(JSON, nullable=True)
    previous_metrics = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


Index("idx_analysis_source_created", IssueAnalysis.prediction_source, IssueAnalysis.created_at)
