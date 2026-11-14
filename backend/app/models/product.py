from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    unit = Column(String(50))
    specifications = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("ProductionBatch", back_populates="product")
    complaints = relationship("Complaint", back_populates="product")


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    country = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("ProductionBatch", back_populates="facility")
    production_lines = relationship("ProductionLine", back_populates="facility")


class ProductionLine(Base):
    __tablename__ = "production_lines"

    id = Column(Integer, primary_key=True, index=True)
    line_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    facility = relationship("Facility", back_populates="production_lines")
    batches = relationship("ProductionBatch", back_populates="production_line")


class ProductionBatch(Base):
    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(100), unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    lot_number = Column(String(100))
    production_date = Column(DateTime)
    expiry_date = Column(DateTime)
    quantity_produced = Column(Float)
    unit = Column(String(50))
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True)
    production_line_id = Column(Integer, ForeignKey("production_lines.id"), nullable=True)
    status = Column(String(50), default="released")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="batches")
    facility = relationship("Facility", back_populates="batches")
    production_line = relationship("ProductionLine", back_populates="batches")
    complaints = relationship("Complaint", back_populates="batch")
