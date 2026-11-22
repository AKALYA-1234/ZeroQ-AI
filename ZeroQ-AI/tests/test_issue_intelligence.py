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

from conftest import submit, incident  # shared helpers

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
    # Uninformative text: weak ML guess, no LLM, no symptom → undetermined, never a fabricated category.
    cid = submit(env, "Hmm", "qwerty asdf zxcv")
    a = incident(env, cid)["analysis"]
    assert a["is_low_confidence"] is True
    assert a["prediction_source"] == "undetermined"
    assert a["predicted_category"] is None and a["predicted_root_cause"] is None
    assert a["predicted_severity"] is None
    assert "ML confidence" in a["fallback_reason"]
    assert a["ml_result"]["category"]          # the ML best guess stays visible as evidence only


def test_llm_failure_falls_back_to_symptom_rules(env, monkeypatch):
    # Force "ML unsure" so the LLM is attempted; it fails, and symptom rules must take over.
    monkeypatch.setattr(settings, "ML_CONFIDENCE_THRESHOLD", 1.01)

    class _Failing:
        class beta:
            class messages:
                @staticmethod
                def parse(**kw):
                    raise RuntimeError("provider down")
    llm.set_client(_Failing())
    llm.reset_circuit()
    try:
        cid = submit(env, "Kiosk", "The conveyor machine is making a grinding noise and vibrating")
    finally:
        llm.set_client(None)
        llm.reset_circuit()
    a = incident(env, cid)["analysis"]
    assert a["is_low_confidence"] is True, a["fallback_reason"]
    assert a["prediction_source"] == "rules", (a["fallback_reason"], a["symptoms"], a["confidence"])
    assert a["predicted_category"] == "Machine / Equipment Abnormality"
    assert "LLM unavailable" in a["fallback_reason"]


class _FakeUsage:
    input_tokens, output_tokens = 1200, 300


class _FakeResponse:
    def __init__(self, parsed):
        self.parsed_output, self.stop_reason = parsed, "end_turn"
        self.usage, self.model = _FakeUsage(), "claude-opus-5-5"


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
                     params={"start": "2025-01-01", "end": "2025-12-31", "category": "Packaging Defect",
                             "scope": "imported"})
    assert res.status_code == 200
    body = res.json()
    assert body["issues"] and all(c["category"] == "Packaging Defect" for c in body["category_distribution"])
    assert client.get("/api/admin/intelligence/kpis", headers=env["admin_h"],
                      params={"start": "not-a-date"}).status_code == 422


def test_llm_circuit_opens_after_repeated_failures(env, monkeypatch):
    calls = []

    class _Failing:
        class beta:
            class messages:
                @staticmethod
                def parse(**kw):
                    calls.append(1)
                    raise RuntimeError("provider down")
    monkeypatch.setattr(settings, "LLM_CIRCUIT_FAILURES", 2)
    llm.set_client(_Failing())
    llm.reset_circuit()
    try:
        for _ in range(2):
            with pytest.raises(llm.LLMUnavailable):
                llm.translate("Packet la poochi", "Tanglish")
        assert llm.circuit_status()["state"] == "open"
        assert llm.is_llm_available() is False
        with pytest.raises(llm.LLMUnavailable):
            llm.translate("Packet la poochi", "Tanglish")
        assert len(calls) == 2            # third call short-circuited, no provider request
    finally:
        llm.set_client(None)
        llm.reset_circuit()


def test_llm_usage_and_cost_are_recorded(env):
    fake = _FakeLLM()
    llm.set_client(fake)
    try:
        cid = submit(env, "Kiosk", "The vending kiosk shows error 504 every time")
    finally:
        llm.set_client(None)
    usage = incident(env, cid)["analysis"]["llm_result"]["usage"]
    assert usage and usage[0]["operation"] == "analyze"
    assert usage[0]["input_tokens"] == 1200 and usage[0]["output_tokens"] == 300
    assert usage[0]["estimated_cost_usd"] == round((1200 * 4 + 300 * 20) / 1e6, 6)
