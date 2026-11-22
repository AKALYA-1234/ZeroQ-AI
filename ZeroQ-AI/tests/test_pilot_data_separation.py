"""Pilot data separation: synthetic imports, real customers and test accounts never mix in real-world
metrics or model training (origin.py)."""
from app.core.config import settings
from app.intelligence.learning import build_training_set, learning_status, trainable_resolutions
from app.intelligence.origin import complaint_origin, origin_for_new_submission
from app.models.complaint import Complaint

from conftest import submit

KPI = "/api/admin/intelligence/kpis"
RESOLVE = "/api/admin/intelligence/incidents/{}/resolve"
BODY = {"verified_category": "Packaging Defect", "confirmed_root_cause": "Seal jaw worn",
        "resolution_action": "Replaced seal jaw", "admin_explanation": "We replaced a worn part.",
        "units_contained": 25, "units_at_risk": 100}


def submit_as(env, header_key, title, text):
    data = {"product_id": str(env["ids"]["product"]), "title": title, "description": text}
    r = env["client"].post("/api/complaints/", data=data, headers=env[header_key])
    assert r.status_code == 200, r.text
    return r.json()["complaint_id"]


def kpis(env, scope):
    return env["client"].get(KPI, headers=env["admin_h"], params={"scope": scope}).json()


def test_origin_classification_rules():
    assert complaint_origin("CUS0001", None) == "synthetic"
    assert complaint_origin("CUS0001", "real") == "synthetic"      # a dataset id always means imported
    assert complaint_origin(None, None) == "real"                  # legacy platform row
    assert complaint_origin(None, "test") == "test"


def test_submission_origin_follows_configured_test_accounts(monkeypatch):
    monkeypatch.setattr(settings, "PILOT_TEST_EMAILS", "Demo@Customer.com, qa@corp.example")
    assert origin_for_new_submission("demo@customer.com") == "test"
    assert origin_for_new_submission("QA@corp.example") == "test"
    assert origin_for_new_submission("buyer@real-customer.com") == "real"


def test_real_test_and_synthetic_are_separate_scopes(env, monkeypatch):
    monkeypatch.setattr(settings, "PILOT_TEST_EMAILS", "cust@test.local")      # `cust` is the test account
    real = submit_as(env, "other_h", "Real", "Pack seal was open")
    test = submit_as(env, "cust_h", "QA", "Pack seal was open")
    for cid in (real, test):
        r = env["client"].post(RESOLVE.format(cid), headers=env["admin_h"], json=BODY)
        assert r.status_code == 200, r.text

    live, tst, imp = kpis(env, "live"), kpis(env, "test"), kpis(env, "imported")
    assert live["issue_management"]["total_queries"] == 1
    assert live["business_impact"]["products_saved_units"] == 25         # only the real complaint's units
    assert live["ai_performance"]["verified_predictions"] + live["ai_performance"]["predictions_total"] >= 1
    assert tst["issue_management"]["total_queries"] == 1 and tst["business_impact"]["products_saved_units"] == 25
    assert imp["issue_management"]["total_queries"] == 28                # the seeded synthetic history
    assert kpis(env, "all")["issue_management"]["total_queries"] == 30
    assert imp["business_impact"]["products_saved_units"] == 0           # imports carry no impact figures


def test_test_submissions_never_reach_training_or_learning_status(env, monkeypatch):
    monkeypatch.setattr(settings, "PILOT_TEST_EMAILS", "cust@test.local")
    db = env["Session"]()
    try:
        before = len(trainable_resolutions(db))
        _, _, _, src_before = build_training_set(db)
    finally:
        db.close()
    test = submit_as(env, "cust_h", "QA", "Pack seal was open")
    real = submit_as(env, "other_h", "Real", "Pack seal was open")
    for cid in (test, real):
        assert env["client"].post(RESOLVE.format(cid), headers=env["admin_h"], json=BODY).status_code == 200
    db = env["Session"]()
    try:
        assert len(trainable_resolutions(db)) == before + 1                  # only the real one
        _, _, _, src_after = build_training_set(db)
        assert src_after["admin_verified"] == src_before["admin_verified"] + 1
        assert learning_status(db)["verified_incidents"] == before + 1
    finally:
        db.close()


def test_admin_views_expose_origin_and_legacy_rows_are_classified(env):
    cid = submit_as(env, "other_h", "Real", "Insects inside the packet")
    admin_list = env["client"].get("/api/admin/complaints", headers=env["admin_h"],
                                   params={"search": cid}).json()["items"]
    assert admin_list[0]["data_origin"] == "real"
    synthetic = env["client"].get("/api/admin/complaints", headers=env["admin_h"],
                                  params={"search": "HIS00001"}).json()["items"]
    assert synthetic[0]["data_origin"] == "synthetic"
    detail = env["client"].get(f"/api/admin/intelligence/incidents/{cid}", headers=env["admin_h"]).json()
    assert detail["data_origin"] == "real"
    db = env["Session"]()
    try:                                                                    # legacy NULL origin → real
        pk = db.query(Complaint.id).filter(Complaint.complaint_id == cid).scalar()
        db.query(Complaint).filter(Complaint.id == pk).update({"data_origin": None})
        db.commit()
    finally:
        db.close()
    assert kpis(env, "live")["issue_management"]["total_queries"] >= 1


def test_test_account_domains_match_whole_domains_only(monkeypatch):
    monkeypatch.setattr(settings, "PILOT_TEST_EMAILS", "demo@customer.com, @example.com")
    assert origin_for_new_submission("anyone@example.com") == "test"
    assert origin_for_new_submission("ANYONE@Example.com") == "test"
    assert origin_for_new_submission("someone@notexample.com") == "real"       # suffix must be a whole domain
    assert origin_for_new_submission("buyer@acme.com") == "real"


def test_mark_test_reclassifies_existing_submissions_without_deleting(env):
    from app.core import accounts
    cid = submit_as(env, "other_h", "Validation", "Pack seal was open")            # lands as "real"
    assert kpis(env, "live")["issue_management"]["total_queries"] >= 1
    db = env["Session"]()
    try:
        before_total = db.query(Complaint).count()
        msg = accounts.mark_test(db, "other@test.local")
        assert "marked" in msg
        row = db.query(Complaint).filter(Complaint.complaint_id == cid).one()
        assert row.data_origin == "test"
        assert db.query(Complaint).count() == before_total                        # nothing deleted
    finally:
        db.close()
    live_ids = env["client"].get("/api/admin/complaints", headers=env["admin_h"], params={"search": cid}).json()["items"]
    assert live_ids[0]["data_origin"] == "test"
