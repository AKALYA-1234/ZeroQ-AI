#!/usr/bin/env python3
"""Initialize ZeroQ AI database tables and indexes"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app.database.base import Base
from app.database.connection import engine
from app.models import user, product, complaint, investigation, corrective_action, notification

def init_db():
    print(f"Creating database tables and indexes on {engine.dialect.name}...")
    Base.metadata.create_all(bind=engine)
    print("Database tables and indexes created successfully!")

if __name__ == "__main__":
    init_db()
