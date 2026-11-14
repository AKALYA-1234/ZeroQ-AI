from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255))
    message = Column(Text)
    notification_type = Column(String(100))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    full_name = Column(String(255))
    contact_number = Column(String(50))
    organization = Column(String(255))
    job_title = Column(String(255))
    country = Column(String(100))
    city = Column(String(100))
    address = Column(Text)
    
    pref_complaint_submission = Column(Boolean, default=True)
    pref_status_updates = Column(Boolean, default=True)
    pref_investigation_updates = Column(Boolean, default=True)
    pref_resolution = Column(Boolean, default=True)
    pref_email = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="customer_profile")


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String(50), unique=True, index=True)
    model_version = Column(String(50))
    input_features = Column(JSON)
    prediction_result = Column(JSON)
    confidence_score = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255))
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    details = Column(JSON)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
