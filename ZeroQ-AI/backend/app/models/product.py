from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), index=True)
    unit = Column(String(50), default="case")
    storage_condition = Column(String(100), nullable=True)
    shelf_life_days = Column(Integer, nullable=True)
    specifications = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("ProductionBatch", back_populates="product")
    complaints = relationship("Complaint", back_populates="product")


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    state = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    country = Column(String(100), default="India")
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("ProductionBatch", back_populates="facility")
    production_lines = relationship("ProductionLine", back_populates="facility")


class ProductionLine(Base):
    __tablename__ = "production_lines"

    id = Column(Integer, primary_key=True, index=True)
    line_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False)
    line_type = Column(String(100), nullable=True)
    commissioned_year = Column(Integer, nullable=True)
    operating_status = Column(String(50), default="Active")
    facility_id = Column(Integer, ForeignKey("facilities.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    facility = relationship("Facility", back_populates="production_lines")
    batches = relationship("ProductionBatch", back_populates="production_line")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(String(50), unique=True, index=True)
    name = Column(String(255), nullable=False)
    material_type = Column(String(100), index=True)
    approved_supplier_id = Column(String(100), nullable=True)
    criticality = Column(String(50), default="Medium")
    shelf_life_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductionBatch(Base):
    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(100), unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True, index=True)
    production_line_id = Column(Integer, ForeignKey("production_lines.id"), nullable=True, index=True)
    lot_number = Column(String(100), nullable=True)
    production_date = Column(DateTime, index=True)
    production_shift = Column(String(50), nullable=True)
    units_produced = Column(Integer, default=0)
    quantity_produced = Column(Float, nullable=True)
    unit = Column(String(50), default="case")
    machine_id = Column(String(50), nullable=True)
    process_temperature_c = Column(Float, nullable=True)
    ambient_humidity_pct = Column(Float, nullable=True)
    line_pressure_bar = Column(Float, nullable=True)
    sealing_temperature_c = Column(Float, nullable=True)
    days_since_last_maintenance = Column(Integer, nullable=True)
    packaging_material_id = Column(String(50), nullable=True)
    raw_material_id = Column(String(50), nullable=True)
    supplier_quality_grade = Column(String(50), nullable=True)
    process_deviation_flag = Column(Integer, default=0)
    planned_dispatch_date = Column(DateTime, nullable=True)
    complaint_count_linked = Column(Integer, default=0)
    complaint_occurred = Column(Integer, default=0)
    expiry_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="released")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="batches")
    facility = relationship("Facility", back_populates="batches")
    production_line = relationship("ProductionLine", back_populates="batches")
    complaints = relationship("Complaint", back_populates="batch")


class QualityInspection(Base):
    __tablename__ = "quality_inspections"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(String(50), unique=True, index=True)
    batch_id = Column(String(100), index=True)
    inspection_date = Column(DateTime, nullable=True, index=True)
    inspection_stage = Column(String(100), nullable=True)
    quality_parameter = Column(String(100), nullable=True)
    measured_value = Column(Float, nullable=True)
    unit_of_measure = Column(String(50), nullable=True)
    acceptable_min = Column(Float, nullable=True)
    acceptable_max = Column(Float, nullable=True)
    inspection_result = Column(String(50), nullable=True, index=True)
    inspector_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Index("idx_batch_prod_date", ProductionBatch.product_id, ProductionBatch.production_date)
Index("idx_batch_fac_line", ProductionBatch.facility_id, ProductionBatch.production_line_id)
