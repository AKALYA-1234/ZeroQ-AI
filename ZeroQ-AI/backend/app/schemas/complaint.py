from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ComplaintCreate(BaseModel):
    product_id: int
    batch_number: Optional[str] = None
    title: str
    description: str
    category: str
    reported_severity: str
    purchase_date: Optional[datetime] = None
    date_of_issue: Optional[datetime] = None
    place_of_purchase: Optional[str] = None
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    customer_organization: Optional[str] = None

class ComplaintStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    is_customer_visible: bool = False
    assigned_to: Optional[str] = None
    admin_severity: Optional[str] = None
    internal_notes: Optional[str] = None
    customer_visible_update: Optional[str] = None

class AttachmentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class StatusHistoryResponse(BaseModel):
    id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    is_customer_visible: bool
    notes: Optional[str] = None
    changed_at: datetime

    class Config:
        from_attributes = True

class ComplaintResponse(BaseModel):
    id: int
    complaint_id: str
    record_type: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_organization: Optional[str] = None
    product_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    reported_severity: Optional[str] = None
    place_of_purchase: Optional[str] = None
    purchase_date: Optional[datetime] = None
    date_of_issue: Optional[datetime] = None
    status: str
    submitted_date: datetime
    last_updated: datetime
    resolved_date: Optional[datetime] = None
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True
