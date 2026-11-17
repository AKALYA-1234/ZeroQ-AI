from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(String(50), unique=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True, index=True)
    complaint_code = Column(String(50), index=True, nullable=True)
    
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    investigation_type = Column(String(100), nullable=True, index=True)
    
    root_cause_category = Column(String(100), nullable=True, index=True)
    root_cause_description = Column(Text, nullable=True)
    is_root_cause_verified = Column(Boolean, default=False)
    
    status = Column(String(100), default="open", index=True)
    priority = Column(String(50), default="medium")
    root_cause_confidence = Column(Float, nullable=True)
    
    opened_date = Column(DateTime, nullable=True, index=True)
    closed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    record_type = Column(String(50), default="admin_created")
    
    complaint = relationship("Complaint", back_populates="investigations")
    corrective_actions = relationship("CorrectiveAction", back_populates="investigation")

Index("idx_inv_status_root", Investigation.status, Investigation.root_cause_category)
