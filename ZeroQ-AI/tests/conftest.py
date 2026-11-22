"""Shared fixtures: an isolated temporary SQLite DB seeded with historical incidents
(shaped like the real import: customer_id + customer PII, no owning user)."""
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.intelligence import classifier as clf_registry
from app.intelligence import llm
from app.intelligence.retrieval import invalidate_index
from app.main import app
from app.models.complaint import Complaint
from app.models.corrective_action import CorrectiveAction
from app.models.investigation import Investigation
from app.models.product import Product
from app.models.user import User

HISTORY = [
    # (subcategory, category, description, root cause, action, effectiveness, severity)
    ("Leakage", "Packaging Defect", "Customer reported product leakage from the sealed pack.",
     "Incorrect sealing pressure", "Adjust sealing pressure to approved specification", "effective", "medium"),
    ("Poor Sealing", "Packaging Defect", "Pack seal was found partially open after receipt.",
     "Sealing temperature variation", "Calibrate sealing temperature controller", "effective", "medium"),
    ("Insect Presence", "Infestation", "Customer reported an insect inside the product packaging.",
     "Storage area pest control gap", "Fumigate storage area and review pest control", "effective", "high"),
    ("Plastic Fragment", "Foreign Matter / Contamination", "A suspected plastic fragment was reported in the product.",
     "Equipment integrity issue", "Replace damaged scraper and add sieve check", "partially_effective", "high"),
    ("Off Odour", "Sensory Defect", "An unusual odour was noticed when the package was opened.",
     "Raw material variation", "Quarantine raw material lot", "effective", "medium"),
    ("Underweight Pack", "Weight / Quantity", "Net weight was below the declared quantity.",
     "Filling machine calibration drift", "Recalibrate filling machine", "effective", "low"),
    ("Incorrect Label", "Packaging Defect", "Product label information did not match the pack contents.",
     "Packaging material defect", "Line clearance check for labels", "ineffective", "medium"),
]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("intel")
    engine = create_engine(f"sqlite:///{tmp / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = TestSession()
    admin = User(email="admin@test.local", hashed_password="x", role="admin")
    cust = User(email="cust@test.local", hashed_password="x", role="customer")
    other = User(email="other@test.local", hashed_password="x", role="customer")
    db.add_all([admin, cust, other])
    product = Product(product_id="PRD001", name="Classic Biscuits", category="Biscuits")
    db.add(product)
    db.flush()
    base = datetime(2025, 1, 1)
    n = 0
    for rep in range(4):
        for sub, cat, desc, rc, action, eff, sev in HISTORY:
            n += 1
            c = Complaint(complaint_id=f"HIS{n:05d}", record_type="historical", product_id=product.id,
                          title=f"{cat} - {sub}", description=desc,
                          customer_id=f"CUS{n:04d}", customer_name=f"Customer CUS{n:04d}",
                          customer_email=f"cus{n:04d}@enterprise.com", category=cat, complaint_subcategory=sub,
                          reported_severity=sev, status="resolved", units_affected=10,
                          submitted_date=base + timedelta(days=n * 3),
                          resolved_date=base + timedelta(days=n * 3 + 5))
            db.add(c)
            db.flush()
            inv = Investigation(investigation_id=f"INV{n:05d}", complaint_id=c.id, root_cause_description=rc,
                                is_root_cause_verified=True, status="closed")
            db.add(inv)
            db.flush()
            db.add(CorrectiveAction(capa_id=f"CAPA{n:05d}", complaint_id=c.id, investigation_id=inv.id,
                                    description=action, effectiveness_status=eff, status="completed"))
    db.commit()
    ids = {"admin": admin.id, "cust": cust.id, "other": other.id, "product": product.id}
    db.close()

    def override_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    old_dir, old_backend = clf_registry.MODEL_DIR, settings.EMBEDDING_BACKEND
    clf_registry.MODEL_DIR = str(tmp / "models")
    settings.EMBEDDING_BACKEND = "tfidf"
    clf_registry.clear_cache()
    invalidate_index()
    llm.set_client(None)
    app.dependency_overrides[get_db] = override_db

    def token(uid, role):
        return create_access_token({"sub": str(uid), "role": role})

    yield {
        "client": TestClient(app), "Session": TestSession, "ids": ids,
        "admin_h": {"Authorization": f"Bearer {token(ids['admin'], 'admin')}"},
        "cust_h": {"Authorization": f"Bearer {token(ids['cust'], 'customer')}"},
        "other_h": {"Authorization": f"Bearer {token(ids['other'], 'customer')}"},
        "cust_token": token(ids["cust"], "customer"),
    }

    app.dependency_overrides.pop(get_db, None)
    clf_registry.MODEL_DIR, settings.EMBEDDING_BACKEND = old_dir, old_backend
    clf_registry.clear_cache()
    invalidate_index()
    llm.set_client(None)
    engine.dispose()


def submit(env, title, description, **extra):
    data = {"product_id": str(env["ids"]["product"]), "title": title, "description": description, **extra}
    res = env["client"].post("/api/complaints/", data=data, headers=env["cust_h"])
    assert res.status_code == 200, res.text
    return res.json()["complaint_id"]


def incident(env, cid):
    res = env["client"].get(f"/api/admin/intelligence/incidents/{cid}", headers=env["admin_h"])
    assert res.status_code == 200, res.text
    return res.json()
