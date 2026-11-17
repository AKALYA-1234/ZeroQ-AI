from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="customer", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer_profile = relationship("CustomerProfile", back_populates="user", uselist=False)
    complaints = relationship("Complaint", back_populates="submitter")
    notifications = relationship("Notification", back_populates="user")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_type = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True, index=True)
    customer_tenure_years = Column(Integer, nullable=True)
    account_tier = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
