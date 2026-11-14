#!/usr/bin/env python3
"""Create demo users and sample demonstration records for ZeroQ AI"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database.connection import SessionLocal, engine
from app.database.base import Base
from app.models.user import User
from app.models.product import Product, ProductionBatch, Facility
from app.models.complaint import Complaint, ComplaintStatusHistory, ComplaintAttachment
from app.models.investigation import Investigation
from app.models.corrective_action import CorrectiveAction
from app.models.notification import CustomerProfile, ModelPrediction, Notification, AuditLog
from app.core.security import get_password_hash
from app.ml.model_service import is_model_available, predict_complaint_risk

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ── 1. Create demo customer (Sarah Jenkins • Apex Dynamics) ──────────
        customer_user = db.query(User).filter(User.email == "demo@customer.com").first()
        if not customer_user:
            customer_user = User(
                email="demo@customer.com",
                hashed_password=get_password_hash("DemoCustomer2024!"),
                role="customer",
                is_active=True
            )
            db.add(customer_user)
            db.flush()
            profile = CustomerProfile(
                user_id=customer_user.id,
                full_name="Sarah Jenkins",
                organization="Apex Dynamics Corp.",
                job_title="Director of Quality & Procurement",
                contact_number="+1 (555) 382-9014",
                country="United States",
                city="Austin, TX",
                address="4800 Freidrich Ln, Suite 200"
            )
            db.add(profile)
            print("Created demo customer: demo@customer.com / DemoCustomer2024! (Sarah Jenkins • Apex Dynamics)")
        else:
            print("Demo customer exists")

        # ── 2. Create demo admin ──────────────────────────────────────────────
        admin_user = db.query(User).filter(User.email == "admin@zeroq.com").first()
        if not admin_user:
            admin_user = User(
                email="admin@zeroq.com",
                hashed_password=get_password_hash("AdminZeroQ2024!"),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            print("Created demo admin: admin@zeroq.com / AdminZeroQ2024!")
        else:
            print("Demo admin exists")

        # ── 3. Seed Products ──────────────────────────────────────────────────
        sample_products = [
            ("QA-8812-X", "Precision Servo Actuator Series X (Product A)", "Industrial Robotics", "pcs", "High-precision rotary servo actuator with integrated encoder."),
            ("QA-4401-B", "Heavy-Duty Hydraulic Valve Unit (Product B)", "Fluid Dynamics", "units", "Electro-hydraulic proportional direction control valve manifold."),
            ("QA-1290-C", "Sensor Array Module V3 (Product C)", "Sensors & Telemetry", "sets", "Multi-axis vibrational and acoustic sensor telemetry assembly."),
            ("QA-9920-D", "Fiber Reinforced Composites (Product D)", "Materials & Structural", "meters", "High-tensile carbon-aramid woven composite for aerospace casing."),
            ("QA-5500-E", "Pneumatic Pressure Regulator E5", "Pneumatics", "pcs", "Closed-loop pressure regulating module with optical bypass indicator.")
        ]

        products_map = {}
        for p_code, p_name, p_cat, p_unit, p_desc in sample_products:
            prod = db.query(Product).filter(Product.product_id == p_code).first()
            if not prod:
                prod = Product(
                    product_id=p_code,
                    name=p_name,
                    category=p_cat,
                    unit=p_unit,
                    description=p_desc,
                    is_active=True
                )
                db.add(prod)
                db.flush()
            products_map[p_code] = prod
        print("Seeded product catalog.")

        # ── 4. Seed Facility & Batches ────────────────────────────────────────
        facility = db.query(Facility).filter(Facility.facility_id == "FAC-01").first()
        if not facility:
            facility = Facility(
                facility_id="FAC-01",
                name="Main Plant - Facility Alpha",
                location="Austin Technology Park, Texas",
                country="United States"
            )
            db.add(facility)
            db.flush()

        batch_1 = db.query(ProductionBatch).filter(ProductionBatch.batch_id == "LOT-2026-88482").first()
        if not batch_1:
            batch_1 = ProductionBatch(
                batch_id="LOT-2026-88482",
                product_id=products_map["QA-8812-X"].id,
                lot_number="LOT-2026-88482",
                production_date=datetime.utcnow() - timedelta(days=60),
                quantity_produced=5000,
                unit="pcs",
                facility_id=facility.id,
                status="released"
            )
            db.add(batch_1)

        # ── 5. Seed Customer Complaints Matching Screenshot UI ────────────────
        complaints_data = [
            {
                "complaint_id": "ZQ-CMP-2026-00125",
                "product_code": "QA-8812-X",
                "category": "Packaging Issue",
                "severity": "high",
                "title": "Seal integrity breach and carton deformation on Lot #88482",
                "description": "Upon receiving pallet shipment #PL-9021, two outer cartons exhibited crushed structural corners. Upon opening batch pack #88482, the protective inner seal was punctured and hydraulic fluid residue was observed on the secondary gasket. The unit cannot pass initial bench inspection.",
                "place_of_purchase": "Direct Enterprise Order / Distribution Hub 04",
                "purchase_date": datetime.utcnow() - timedelta(days=30),
                "date_of_issue": datetime.utcnow() - timedelta(days=2),
                "status": "under_review",
                "submitted_days_ago": 2,
                "notes": "Quality assurance initial review and triage underway."
            },
            {
                "complaint_id": "ZQ-CMP-2026-00124",
                "product_code": "QA-4401-B",
                "category": "Product Defect",
                "severity": "medium",
                "title": "Pressure variance on manifold valve port 4",
                "description": "Minor pressure drop observed under intermittent 180 bar duty cycle testing. Leakage rate within tolerance but above nominal specifications.",
                "place_of_purchase": "Regional Depot Midwest",
                "purchase_date": datetime.utcnow() - timedelta(days=45),
                "date_of_issue": datetime.utcnow() - timedelta(days=4),
                "status": "resolved",
                "submitted_days_ago": 4,
                "notes": "Resolved with replacement O-ring batch and certified calibration."
            },
            {
                "complaint_id": "ZQ-CMP-2026-00123",
                "product_code": "QA-1290-C",
                "category": "Performance Issue",
                "severity": "low",
                "title": "Telemetry baseline drift on secondary vibrational channel",
                "description": "Signal attenuation noted when ambient operating temperature exceeds 42C. Re-calibration recommended.",
                "place_of_purchase": "Global Supplies Online",
                "purchase_date": datetime.utcnow() - timedelta(days=60),
                "date_of_issue": datetime.utcnow() - timedelta(days=6),
                "status": "investigation_in_progress",
                "submitted_days_ago": 6,
                "notes": "Laboratory bench diagnostics in progress at Regional Testing Lab."
            },
            {
                "complaint_id": "ZQ-CMP-2026-00122",
                "product_code": "QA-8812-X",
                "category": "Material Quality Issue",
                "severity": "critical",
                "title": "Micro-fracture detected in stator housing alloy",
                "description": "Acoustic emission testing identified sub-surface micro-fracturing along stator flange mounting point during 100% stress validation.",
                "place_of_purchase": "Direct Enterprise Order",
                "purchase_date": datetime.utcnow() - timedelta(days=90),
                "date_of_issue": datetime.utcnow() - timedelta(days=9),
                "status": "corrective_action_initiated",
                "submitted_days_ago": 9,
                "notes": "CAPA-2026-0018 initiated for foundry casting inspection."
            },
            {
                "complaint_id": "ZQ-CMP-2026-00121",
                "product_code": "QA-9920-D",
                "category": "Packaging Issue",
                "severity": "medium",
                "title": "Moisture barrier desiccator depletion",
                "description": "Desiccator pouch found saturated upon arrival. Composite material packaging humidity indicator read 45% RH.",
                "place_of_purchase": "Coastal Freight Hub",
                "purchase_date": datetime.utcnow() - timedelta(days=120),
                "date_of_issue": datetime.utcnow() - timedelta(days=12),
                "status": "resolved",
                "submitted_days_ago": 12,
                "notes": "Batch quarantined, replacement dispatched, vendor packaging specs updated."
            }
        ]

        for cd in complaints_data:
            existing = db.query(Complaint).filter(Complaint.complaint_id == cd["complaint_id"]).first()
            if not existing:
                prod = products_map.get(cd["product_code"])
                sub_date = datetime.utcnow() - timedelta(days=cd["submitted_days_ago"])
                complaint = Complaint(
                    complaint_id=cd["complaint_id"],
                    record_type="customer_submitted",
                    submitted_by_user_id=customer_user.id,
                    customer_name=customer_user.customer_profile.full_name if customer_user.customer_profile else "Sarah Jenkins",
                    customer_email=customer_user.email,
                    customer_contact=customer_user.customer_profile.contact_number if customer_user.customer_profile else "+1 (555) 382-9014",
                    customer_organization=customer_user.customer_profile.organization if customer_user.customer_profile else "Apex Dynamics Corp.",
                    product_id=prod.id if prod else None,
                    title=cd["title"],
                    description=cd["description"],
                    category=cd["category"],
                    reported_severity=cd["severity"],
                    place_of_purchase=cd["place_of_purchase"],
                    purchase_date=cd["purchase_date"],
                    date_of_issue=cd["date_of_issue"],
                    status=cd["status"],
                    submitted_date=sub_date,
                    last_updated=sub_date + timedelta(hours=6),
                    customer_visible_update=cd["notes"]
                )
                db.add(complaint)
                db.flush()

                hist = ComplaintStatusHistory(
                    complaint_id=complaint.id,
                    old_status=None,
                    new_status=cd["status"],
                    changed_by="Quality Assurance Team",
                    changed_by_role="quality_manager",
                    notes=cd["notes"],
                    is_customer_visible=True,
                    changed_at=sub_date + timedelta(hours=6)
                )
                db.add(hist)

                # Connect with XGBoost Model for automated risk prediction record
                if is_model_available():
                    try:
                        pred_res = predict_complaint_risk(
                            product_name=prod.name if prod else None,
                            complaint_category=cd["category"],
                            severity=cd["severity"],
                            description=cd["description"],
                            title=cd["title"]
                        )
                        if pred_res.get("status") == "success":
                            complaint.admin_severity = pred_res.get("predicted_severity")
                            pred_entry = ModelPrediction(
                                prediction_id=f"PRED-2026-{complaint.id:04d}",
                                model_version=pred_res.get("model_version"),
                                input_features={
                                    "complaint_id": complaint.complaint_id,
                                    "product": prod.name if prod else None,
                                    "category": cd["category"],
                                    "severity": cd["severity"],
                                },
                                prediction_result=pred_res,
                                confidence_score=str(pred_res.get("confidence")),
                                created_by=customer_user.id
                            )
                            db.add(pred_entry)
                    except Exception as me:
                        print(f"Prediction warning: {me}")

        db.commit()
        print("\nDatabase seeded successfully with demo users, catalog products, and initial complaints!")
        print("Customer login: demo@customer.com / DemoCustomer2024!")
        print("Admin login:    admin@zeroq.com / AdminZeroQ2024!")
    except Exception as e:
        db.rollback()
        print(f"Seeding error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
