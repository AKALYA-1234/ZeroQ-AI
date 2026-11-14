from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(Integer, primary_key=True, index=True)
    capa_id = Column(String(50), unique=True, index=True)
    
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=True)
    
    action_type = Column(String(50), default="corrective")
    title = Column(String(500))
    description = Column(Text)
    priority = Column(String(50))
    
    assigned_to = Column(String(255))
    deadline = Column(DateTime, nullable=True)
    
    status = Column(String(100), default="pending")
    completion_evidence = Column(Text, nullable=True)
    
    effectiveness_status = Column(String(100), nullable=True)
    effectiveness_evidence = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    record_type = Column(String(50), default="admin_created")
    
    complaint = relationship("Complaint", back_populates="corrective_actions")
    investigation = relationship("Investigation", back_populates="corrective_actions")
