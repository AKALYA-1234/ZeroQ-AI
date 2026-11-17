#!/usr/bin/env python3
"""
ZeroQ AI - Seed Demo Users Script
Creates or updates demo users (admin and customer) connected to real database records.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database.connection import SessionLocal, engine
from app.database.base import Base
from app.models.user import User
from app.models.notification import CustomerProfile
from app.models.complaint import Complaint
from app.core.security import get_password_hash

def seed_demo_users():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Seed or update demo customer
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
            print("Created demo customer: demo@customer.com / DemoCustomer2024!")
        else:
            customer_user.hashed_password = get_password_hash("DemoCustomer2024!")
            customer_user.is_active = True
            db.flush()
            print("Updated demo customer credentials: demo@customer.com / DemoCustomer2024!")

        # Profile
        profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == customer_user.id).first()
        if not profile:
            profile = CustomerProfile(
                user_id=customer_user.id,
                full_name="Sarah Jenkins",
                organization="Apex Dynamics Corp.",
                job_title="Director of Quality & Procurement",
                contact_number="+1 (555) 382-9014",
                country="India",
                city="Chennai",
                address="4800 Anna Salai, Industrial Sector"
            )
            db.add(profile)
            db.flush()
            print("Created customer profile for Sarah Jenkins (Apex Dynamics Corp.)")
        
        # Link CUS0001 complaints to demo customer for live portal interaction
        demo_complaints = db.query(Complaint).filter(Complaint.customer_id == "CUS0001").all()
        for c in demo_complaints:
            c.submitted_by_user_id = customer_user.id
            c.customer_name = profile.full_name
            c.customer_email = customer_user.email
            c.customer_organization = profile.organization
        db.flush()
        print(f"Linked {len(demo_complaints)} real dataset complaints to demo customer.")

        # 2. Seed or update demo admin
        admin_user = db.query(User).filter(User.email == "admin@zeroq.com").first()
        if not admin_user:
            admin_user = User(
                email="admin@zeroq.com",
                hashed_password=get_password_hash("AdminZeroQ2024!"),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.flush()
            print("Created demo admin: admin@zeroq.com / AdminZeroQ2024!")
        else:
            admin_user.hashed_password = get_password_hash("AdminZeroQ2024!")
            admin_user.is_active = True
            db.flush()
            print("Updated demo admin credentials: admin@zeroq.com / AdminZeroQ2024!")

        db.commit()
        print("\nDemo users successfully configured with real dataset associations!")
        print("Customer login: demo@customer.com / DemoCustomer2024!")
        print("Admin login:    admin@zeroq.com / AdminZeroQ2024!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding demo users: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_users()
