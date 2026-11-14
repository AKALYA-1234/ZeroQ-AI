from pydantic import BaseModel
from typing import Optional

class CustomerProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    contact_number: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None

class CustomerProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    contact_number: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    pref_complaint_submission: bool = True
    pref_status_updates: bool = True
    pref_investigation_updates: bool = True
    pref_resolution: bool = True
    pref_email: bool = True

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class NotificationPreferences(BaseModel):
    pref_complaint_submission: bool = True
    pref_status_updates: bool = True
    pref_investigation_updates: bool = True
    pref_resolution: bool = True
    pref_email: bool = True
