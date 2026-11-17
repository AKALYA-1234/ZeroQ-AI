import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/api/auth/login", json={
        "email": "admin@zeroq.com",
        "password": "AdminZeroQ2024!"
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def customer_token():
    res = client.post("/api/auth/login", json={
        "email": "demo@customer.com",
        "password": "DemoCustomer2024!"
    })
    assert res.status_code == 200, f"Customer login failed: {res.text}"
    return res.json()["access_token"]

# ── Health & Products ─────────────────────────────────────────────────────

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_list_products():
    res = client.get("/api/products/")
    assert res.status_code == 200
    products = res.json()
    assert len(products) == 20, f"Expected 20 real products, got {len(products)}"
    assert any(p["name"] == "Classic Biscuits" for p in products)

# ── Customer Endpoints ────────────────────────────────────────────────────

def test_customer_profile(customer_token):
    headers = {"Authorization": f"Bearer {customer_token}"}
    res = client.get("/api/customer/profile", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "demo@customer.com"
    assert "Sarah Jenkins" in data["full_name"]

def test_customer_complaints_summary(customer_token):
    headers = {"Authorization": f"Bearer {customer_token}"}
    res = client.get("/api/complaints/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert data["total"] > 0, "Customer should have real complaints linked"

def test_customer_nlp_query_prediction(customer_token):
    headers = {"Authorization": f"Bearer {customer_token}"}
    res = client.post(
        "/api/customer/query-prediction",
        json={"query": "Predict defect risk for Classic Biscuits produced in Pune on Night shift with temperature 135C"},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "complaint_probability" in data
    assert "explanation" in data
    assert len(data["clues_extracted"]) >= 3

def test_customer_query_history(customer_token):
    headers = {"Authorization": f"Bearer {customer_token}"}
    res = client.get("/api/customer/query-predictions/history", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1

# ── Admin Endpoints & Filters ─────────────────────────────────────────────

def test_admin_dashboard(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["kpis"]["total_complaints"] >= 6000
    assert len(data["complaints_by_year"]) > 0
    assert len(data["complaints_by_category"]) > 0

def test_admin_complaints_list(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/complaints?page=1&per_page=20", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 6000
    assert len(data["items"]) == 20

def test_admin_analytics(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/analytics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "by_year" in data
    assert "by_category" in data

def test_admin_risk_assessment(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/risk-assessment/batches", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "batches" in data
    assert len(data["batches"]) > 0

def test_admin_capa_list(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/capa?page=1&per_page=15", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3500

def test_admin_root_causes(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/root-causes", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0

def test_admin_prediction_status_and_model_info(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/predictions/model-info", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["model_deployed"] is True
    assert len(data["feature_importance"]) > 0

# ── General Prediction Endpoints ──────────────────────────────────────────

def test_prediction_status(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/predictions/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "active"

def test_prediction_batch_eval(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/predictions/predict", json={"batch_id": "BAT000004"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "complaint_probability" in data["prediction"]
