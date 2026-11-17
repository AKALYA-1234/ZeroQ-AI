import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.database.connection import SessionLocal
from app.models.complaint import Complaint
from app.models.product import Product

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/api/auth/login", json={
        "email": "admin@zeroq.com",
        "password": "AdminZeroQ2024!"
    })
    assert res.status_code == 200
    return res.json()["access_token"]

def test_filter_combinations_match_db_queries_100_percent(admin_token):
    """
    Acceptance Criteria:
    Filter results match direct DB queries on 100% of tested combinations.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    db = SessionLocal()

    # Get sample values from database to test combinations
    products = db.query(Product).limit(3).all()
    categories = ["Packaging Defect", "Sensory Defect", "Physical Defect"]
    severities = ["critical", "high", "medium", "low"]
    statuses = ["resolved", "investigation_in_progress", "under_review"]

    test_combinations = [
        {"category": "Packaging Defect"},
        {"severity": "critical"},
        {"severity": "high"},
        {"status": "resolved"},
        {"status": "investigation_in_progress"},
        {"category": "Sensory Defect", "severity": "medium"},
        {"category": "Physical Defect", "status": "resolved"},
        {"product_id": str(products[0].id)},
        {"product_id": str(products[1].id), "severity": "high"},
        {"category": "Packaging Defect", "severity": "high", "status": "resolved"}
    ]

    total_tested = len(test_combinations)
    total_matched = 0

    try:
        for idx, params in enumerate(test_combinations):
            # 1. Direct DB Query
            q = db.query(Complaint)
            if "category" in params:
                q = q.filter(Complaint.category == params["category"])
            if "severity" in params:
                q = q.filter(Complaint.reported_severity == params["severity"])
            if "status" in params:
                q = q.filter(Complaint.status == params["status"])
            if "product_id" in params:
                q = q.filter(Complaint.product_id == int(params["product_id"]))

            expected_count = q.count()

            # 2. API Query
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            res = client.get(f"/api/admin/complaints?page=1&per_page=1&{query_str}", headers=headers)
            assert res.status_code == 200, f"Filter API failed for {params}: {res.text}"
            
            api_count = res.json().get("total")

            # 3. Assert 100% exact match
            assert api_count == expected_count, (
                f"Filter mismatch on combo #{idx + 1} {params}: API={api_count} vs DB={expected_count}"
            )
            total_matched += 1

        print(f"\n[Filter Validation]: {total_matched}/{total_tested} tested combinations matched direct DB queries 100%!")
        assert total_matched == total_tested
    finally:
        db.close()
