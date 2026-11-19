"""
End-to-end tests for multilingual issue prediction, LLM fallback, historical
retrieval, admin verification/resolution, real-time sync, feedback, learning
and analytics. Runs against an isolated temporary SQLite database.
"""
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
from app.intelligence.learning import build_training_set
from app.intelligence.retrieval import invalidate_index
from app.main import app
from app.models.complaint import Complaint
from app.models.corrective_action import CorrectiveAction
from app.models.intelligence import IssueAnalysis
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
                          title=f"{cat} - {sub}", description=desc, category=cat, complaint_subcategory=sub,
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


# ── 1-4: multilingual submissions ─────────────────────────────────────────

def test_english_query_is_analyzed_and_original_preserved(env):
    text = "The sauce pouch was leaking all over the shopping bag"
    cid = submit(env, "Leaking pouch", text)
    a = incident(env, cid)["analysis"]
    assert a["status"] == "completed"
    assert a["detected_language"] == "en"
    assert text in a["original_text"]
    assert a["predicted_category"] == "Packaging Defect"
    assert a["similar_incidents"], "historical incidents should be retrieved"


def test_tamil_query_detected_and_translated(env):
    text = "பிஸ்கட் பாக்கெட்டில் பூச்சி இருந்தது"
    cid = submit(env, "புகார்", text)
    a = incident(env, cid)["analysis"]
    assert a["detected_language"] == "ta"
    assert a["original_text"].endswith(text)          # original kept verbatim
    assert "insect" in a["english_text"].lower()
    assert a["translation_method"] == "glossary"
    assert a["predicted_category"] == "Infestation"


def test_hindi_query_detected(env):
    cid = submit(env, "शिकायत", "सॉस से बदबू आ रही है")
    a = incident(env, cid)["analysis"]
    assert a["detected_language"] == "hi"
    assert a["predicted_category"] == "Sensory Defect"


def test_code_mixed_tanglish_query(env):
    cid = submit(env, "Line issue", "Machine romba heat aguthu, production output kammiya irukku")
    a = incident(env, cid)["analysis"]
    assert a["detected_language"] == "ta" and a["is_code_mixed"] is True
    assert "Machine overheating" in a["symptoms"]
    assert "Reduced production output" in a["symptoms"]
    assert a["predicted_category"] == "Machine / Equipment Abnormality"
    # No comparable history: don't borrow a root cause from unrelated incidents;
    # recommend the symptom-specific checks instead.
    assert a["predicted_root_cause"] is None
    assert "temperature" in a["recommended_resolution"].lower()
    assert "motor load" in a["recommended_resolution"].lower()


# ── 5-8: prediction paths and retrieval ───────────────────────────────────

def test_ml_identifies_known_issue_with_confidence(env):
    cid = submit(env, "Label problem", "Expiry date printed on the label is wrong")
    a = incident(env, cid)["analysis"]
    assert a["prediction_source"] == "ml"
    assert a["is_low_confidence"] is False
    assert a["confidence"] >= settings.ML_CONFIDENCE_THRESHOLD
    assert a["predicted_root_cause"] == "Packaging material defect"


def test_low_confidence_prediction_is_flagged_without_llm(env):
    cid = submit(env, "Problem", "Not happy, something is off with this")
    a = incident(env, cid)["analysis"]
    assert a["is_low_confidence"] is True
    assert a["prediction_source"] in ("rules", "ml")
    assert "ML confidence" in a["fallback_reason"]


class _FakeResponse:
    def __init__(self, parsed):
        self.parsed_output, self.stop_reason = parsed, "end_turn"


class _FakeLLM:
    def __init__(self):
        self.calls = []
        outer = self

        class _Messages:
            def parse(self, **kw):
                outer.calls.append(kw)
                if kw["output_format"] is llm.LLMTranslation:
                    return _FakeResponse(llm.LLMTranslation(english_text="The vending kiosk shows error 504"))
                return _FakeResponse(llm.LLMIssueAnalysis(
                    english_translation="The vending kiosk shows error 504",
                    issue_summary="Kiosk software error", symptoms=["error screen"],
                    category="Other / New Issue", subcategory="Kiosk Software Error",
                    probable_root_cause="Kiosk backend timeout", severity="low",
                    affected_product=None, recommended_resolution="Restart kiosk service",
                    confidence=0.6, reasoning="No similar historical incident"))

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()


def test_llm_fallback_identifies_unfamiliar_issue(env):
    fake = _FakeLLM()
    llm.set_client(fake)
    try:
        cid = submit(env, "Kiosk", "The vending kiosk shows error 504 every time")
    finally:
        llm.set_client(None)
    a = incident(env, cid)["analysis"]
    assert a["prediction_source"] == "llm"
    assert a["predicted_category"] == "Other / New Issue"
    assert a["predicted_root_cause"] == "Kiosk backend timeout"
    assert a["llm_result"]["reasoning"]
    assert fake.calls and fake.calls[-1]["fallbacks"] == "default"


def test_historical_incidents_ranked_with_evidence(env):
    cid = submit(env, "Seal", "Pack seal was open when I bought it")
    a = incident(env, cid)["analysis"]
    top = a["similar_incidents"][0]
    assert top["subcategory"] in ("Poor Sealing", "Leakage")
    assert top["root_cause"] and top["resolution"]
    assert a["root_cause_distribution"][0]["share"] > 0
    assert any(r["success_rate"] is not None for r in a["resolution_options"])


# ── 9-12: verification, resolution, real-time, analytics ──────────────────

def test_admin_corrects_prediction_and_resolves_with_realtime_update(env):
    client = env["client"]
    cid = submit(env, "Pieces", "Expiry date printed on the label is wrong")
    before = client.get("/api/admin/intelligence/kpis", headers=env["admin_h"]).json()

    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "auth", "token": env["cust_token"]})
        assert ws.receive_json()["type"] == "connected"
        res = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"], json={
            "verified_category": "Other Customer Concern", "verified_subcategory": "Incorrect Product",
            "confirmed_root_cause": "Wrong SKU picked at dispatch",
            "resolution_action": "Replaced the order and retrained dispatch staff",
            "admin_explanation": "We shipped the wrong item; a replacement has been sent.",
            "units_contained": 40, "downtime_avoided_hours": 1.5})
        assert res.status_code == 200, res.text
        event = ws.receive_json()
    assert event["type"] == "complaint.resolved"
    assert event["payload"]["complaint_id"] == cid
    assert event["payload"]["resolution"]["confirmed_root_cause"] == "Wrong SKU picked at dispatch"
    assert event["event_id"]

    resolution = res.json()["resolution"]
    assert resolution["category_correct"] is False
    assert "category" in resolution["corrected_fields"]

    view = client.get(f"/api/complaints/{cid}", headers=env["cust_h"]).json()
    assert view["status"] == "resolved"
    assert view["resolution"]["admin_explanation"].startswith("We shipped")
    assert "predicted_root_cause" not in view["ai_understanding"]  # unverified internals hidden

    after = client.get("/api/admin/intelligence/kpis", headers=env["admin_h"]).json()
    assert after["ai_performance"]["verified_predictions"] == before["ai_performance"]["verified_predictions"] + 1
    assert after["business_impact"]["products_saved_units"] == before["business_impact"]["products_saved_units"] + 40
    assert after["issue_management"]["issues_resolved"] >= before["issue_management"]["issues_resolved"] + 1

    dup = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"], json={
        "verified_category": "Packaging Defect", "confirmed_root_cause": "x" * 5,
        "resolution_action": "y" * 5, "admin_explanation": "z" * 12})
    assert dup.status_code == 409

    fb = client.post(f"/api/complaints/{cid}/feedback", headers=env["cust_h"], json={"rating": 5})
    assert fb.status_code == 200 and fb.json()["satisfied"] is True
    assert client.post(f"/api/complaints/{cid}/feedback", headers=env["cust_h"], json={"rating": 4}).status_code == 409
    sat = client.get("/api/admin/intelligence/kpis", headers=env["admin_h"]).json()["business_impact"]
    assert sat["customer_satisfaction_pct"] == 100.0


def test_feedback_rules(env):
    client = env["client"]
    cid = submit(env, "Weight", "Net weight is lower than printed")
    assert client.post(f"/api/complaints/{cid}/feedback", headers=env["cust_h"],
                       json={"rating": 3}).status_code == 409          # not resolved yet
    assert client.post(f"/api/complaints/{cid}/feedback", headers=env["other_h"],
                       json={"rating": 3}).status_code == 403          # not the owner
    assert client.post(f"/api/complaints/{cid}/feedback", headers=env["cust_h"],
                       json={"rating": 9}).status_code == 422          # validation


def test_resolve_validates_input_and_requires_admin(env):
    client = env["client"]
    cid = submit(env, "x", "Leaking pack")
    bad = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"],
                      json={"verified_category": "Packaging Defect", "confirmed_root_cause": "",
                            "resolution_action": "a", "admin_explanation": "short"})
    assert bad.status_code == 422
    forbidden = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["cust_h"], json={})
    assert forbidden.status_code == 403


def test_websocket_rejects_bad_token(env):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as exc:
        with env["client"].websocket_connect("/api/ws") as ws:
            ws.send_json({"type": "auth", "token": "not-a-token"})
            ws.receive_json()
    assert exc.value.code == 4401


def test_websocket_client_leaving_before_auth_is_handled(env):
    """Regression: a client that disconnects before authenticating must not trigger a second close."""
    import asyncio
    from app.api.intelligence import events_socket
    from starlette.websockets import WebSocketDisconnect as Disconnect

    class _ClosedSocket:
        closed = 0

        async def accept(self):
            pass

        async def receive_json(self):
            raise Disconnect(code=1001)

        async def close(self, code=1000):
            _ClosedSocket.closed += 1
            raise RuntimeError("Unexpected ASGI message 'websocket.close'")

    db = env["Session"]()
    asyncio.run(events_socket(_ClosedSocket(), db=db))  # must not raise
    assert _ClosedSocket.closed == 0


def test_only_verified_incidents_feed_training(env):
    db = env["Session"]()
    try:
        analyses = db.query(IssueAnalysis).count()
        _, _, _, sources = build_training_set(db)
        from app.models.intelligence import IncidentResolution
        assert sources["admin_verified"] == db.query(IncidentResolution).count()
        assert analyses > sources["admin_verified"]  # unverified predictions excluded
    finally:
        db.close()


def test_retrain_is_gated_then_forced(env):
    client = env["client"]
    gated = client.post("/api/admin/intelligence/learning/retrain", headers=env["admin_h"], json={})
    assert gated.status_code == 409
    forced = client.post("/api/admin/intelligence/learning/retrain", headers=env["admin_h"], json={"force": True})
    assert forced.status_code == 200, forced.text
    assert forced.json()["status"] in ("completed", "rejected")
    status = client.get("/api/admin/intelligence/learning/status", headers=env["admin_h"]).json()
    assert status["verified_incidents"] >= 1
    assert len(status["training_runs"]) >= 2  # bootstrap + manual


def test_trends_and_filters(env):
    client = env["client"]
    res = client.get("/api/admin/intelligence/trends", headers=env["admin_h"],
                     params={"start": "2025-01-01", "end": "2025-12-31", "category": "Packaging Defect"})
    assert res.status_code == 200
    body = res.json()
    assert body["issues"] and all(c["category"] == "Packaging Defect" for c in body["category_distribution"])
    assert client.get("/api/admin/intelligence/kpis", headers=env["admin_h"],
                      params={"start": "not-a-date"}).status_code == 422
