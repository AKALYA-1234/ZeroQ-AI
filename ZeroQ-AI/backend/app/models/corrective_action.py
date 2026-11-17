from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(Integer, primary_key=True, index=True)
    capa_id = Column(String(50), unique=True, index=True)
    
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True, index=True)
    complaint_code = Column(String(50), index=True, nullable=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=True, index=True)
    investigation_code = Column(String(50), index=True, nullable=True)
    
    action_type = Column(String(50), default="corrective", index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    preventive_action = Column(Text, nullable=True)
    responsible_department = Column(String(100), nullable=True)
    priority = Column(String(50), default="medium")
    
    assigned_to = Column(String(255), nullable=True)
    action_owner_id = Column(String(50), nullable=True)
    deadline = Column(DateTime, nullable=True)
    action_implementation_date = Column(DateTime, nullable=True)
    effectiveness_review_date = Column(DateTime, nullable=True)
    
    status = Column(String(100), default="pending", index=True)
    completion_evidence = Column(Text, nullable=True)
    
    effectiveness_status = Column(String(100), nullable=True, index=True)
    effectiveness_evidence = Column(Text, nullable=True)
    recurrence_observed_90d = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    record_type = Column(String(50), default="admin_created")
    
    complaint = relationship("Complaint", back_populates="corrective_actions")
    investigation = relationship("Investigation", back_populates="corrective_actions")

Index("idx_capa_status_eff", CorrectiveAction.status, CorrectiveAction.effectiveness_status)
