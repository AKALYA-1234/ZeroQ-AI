from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String(50), unique=True, index=True)
    record_type = Column(String(50), default="customer_submitted", nullable=False)
    
    customer_id = Column(String(50), index=True, nullable=True)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_contact = Column(String(100), nullable=True)
    customer_organization = Column(String(255), nullable=True)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True, index=True)
    
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), index=True, nullable=True)
    complaint_subcategory = Column(String(100), nullable=True)
    reported_severity = Column(String(50), index=True, nullable=True)
    admin_severity = Column(String(50), nullable=True)
    units_affected = Column(Integer, default=1)
    complaint_channel = Column(String(100), nullable=True)
    customer_region = Column(String(100), nullable=True, index=True)
    reported_before_dispatch = Column(Integer, default=0)
    
    purchase_date = Column(DateTime, nullable=True)
    date_of_issue = Column(DateTime, nullable=True)
    place_of_purchase = Column(String(255), nullable=True)
    
    status = Column(String(100), default="submitted", index=True)
    
    submitted_date = Column(DateTime, default=datetime.utcnow, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_date = Column(DateTime, nullable=True)
    
    assigned_to = Column(String(255), nullable=True)
    internal_notes = Column(Text, nullable=True)
    customer_visible_update = Column(Text, nullable=True)
    
    submitter = relationship("User", back_populates="complaints", foreign_keys=[submitted_by_user_id])
    product = relationship("Product", back_populates="complaints")
    batch = relationship("ProductionBatch", back_populates="complaints")
    attachments = relationship("ComplaintAttachment", back_populates="complaint")
    status_history = relationship("ComplaintStatusHistory", back_populates="complaint")
    investigations = relationship("Investigation", back_populates="complaint")
    corrective_actions = relationship("CorrectiveAction", back_populates="complaint")


class ComplaintAttachment(Base):
    __tablename__ = "complaint_attachments"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), index=True)
    filename = Column(String(255))
    original_filename = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)
    content_type = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("Complaint", back_populates="attachments")


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), index=True)
    old_status = Column(String(100), nullable=True)
    new_status = Column(String(100))
    changed_by = Column(String(255))
    changed_by_role = Column(String(50))
    notes = Column(Text, nullable=True)
    is_customer_visible = Column(Boolean, default=False)
    changed_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("Complaint", back_populates="status_history")

Index("idx_complaint_status_sev_cat", Complaint.status, Complaint.reported_severity, Complaint.category)
Index("idx_complaint_prod_fac", Complaint.product_id, Complaint.facility_id)
Index("idx_complaint_sub_date", Complaint.submitted_date)
