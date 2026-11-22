from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

from app.core.security import password_policy_error
from typing import Optional
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=255)
    contact_number: Optional[str] = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        reason = password_policy_error(v)
        if reason:
            raise ValueError(reason)
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    email: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
