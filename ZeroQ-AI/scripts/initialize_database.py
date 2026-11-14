#!/usr/bin/env python3
"""Initialize ZeroQ AI database"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app.database.base import Base
from app.database.connection import engine
from app.models import user, product, complaint, investigation, corrective_action, notification

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
