"""Real-world monitoring: figures computed from admin-verified incidents on real complaints only."""
import pytest

from app.core.config import settings
from app.models.complaint import Complaint, ComplaintStatusHistory
from app.models.intelligence import IncidentResolution, IssueAnalysis, ResolutionFeedback

from conftest import submit

@pytest.fixture(autouse=True)
def _clean_live_data(env):
    """`env` is module-scoped; start every test with no live submissions, analyses or resolutions."""
    db = env["Session"]()
    try:
        live = [pk for (pk,) in db.query(Complaint.id).filter(Complaint.customer_id.is_(None),
                                                               Complaint.record_type == "customer_submitted")]
        for model in (ResolutionFeedback, IncidentResolution, IssueAnalysis):
            db.query(model).filter(model.complaint_id.in_(live)).delete(synchronize_session=False)
        db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id.in_(live)).delete(
            synchronize_session=False)
        db.query(Complaint).filter(Complaint.id.in_(live)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    yield


MON = "/api/admin/intelligence/monitoring"
RESOLVE = "/api/admin/intelligence/incidents/{}/resolve"


def resolve_as(env, cid, category, subcategory=None, **extra):
    body = {"verified_category": category, "verified_subcategory": subcategory, "confirmed_root_cause": "Cause (test)",
            "resolution_action": "Action (test)", "admin_explanation": "Resolved during monitoring tests.", **extra}
    r = env["client"].post(RESOLVE.format(cid), headers=env["admin_h"], json=body)
    assert r.status_code == 200, r.text


def monitoring(env, **params):
    r = env["client"].get(MON, headers=env["admin_h"], params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_empty_state_reports_na_not_zero(env):
    m = monitoring(env)
    assert m["basis"]["verified_incidents"] == 0 and m["basis"]["sample_sufficient"] is False
    assert m["accuracy"]["category"]["value_pct"] is None
    assert m["per_category"] == {} and m["by_language"] == []
    assert "Fewer than 30" in m["basis"]["statement"]


def test_metrics_match_hand_computation(env):
    # 3 seal complaints (predicted Packaging Defect), 1 insect complaint (predicted Infestation)
    seal = [submit(env, "Seal", "Pack seal was open when I bought it") for _ in range(3)]
    bug = submit(env, "Bugs", "Insects inside the packet")
    resolve_as(env, seal[0], "Packaging Defect", "Poor Sealing")              # correct
    resolve_as(env, seal[1], "Packaging Defect", "Poor Sealing")              # correct
    resolve_as(env, seal[2], "Physical Defect", "Broken Product")             # wrong: predicted Packaging
    resolve_as(env, bug, "Infestation", "Insect Presence")                    # correct
    m = monitoring(env)
    assert m["basis"]["verified_incidents"] == 4 and m["basis"]["predictions_assessed"] == 4
    acc = m["accuracy"]["category"]
    assert (acc["value_pct"], acc["n"], acc["reliable"]) == (75.0, 4, False)   # 3/4, too few to be reliable
    assert acc["ci95_pct"][0] < 75.0 < acc["ci95_pct"][1]
    assert m["accuracy"]["incorrect_prediction_rate_pct"] == 25.0
    pc = m["per_category"]
    assert pc["Packaging Defect"]["precision"] == round(2 / 3, 4) and pc["Packaging Defect"]["recall"] == 1.0
    assert pc["Infestation"]["precision"] == 1.0 and pc["Infestation"]["support"] == 1
    assert pc["Physical Defect"]["recall"] == 0.0 and pc["Physical Defect"]["low_sample"] is True
    assert m["corrections"]["by_field"].get("category") == 1
    assert m["by_source"]["ml"]["n"] == 4
    assert m["by_language"][0]["language"] == "English" and m["by_language"][0]["n"] == 4
    assert m["pipeline"]["analyses_total"] >= 4


def test_synthetic_and_test_data_are_excluded_from_live_monitoring(env, monkeypatch):
    monkeypatch.setattr(settings, "PILOT_TEST_EMAILS", "cust@test.local")
    test_cid = submit(env, "QA", "Pack seal was open")                          # cust = test account
    real = env["client"].post("/api/complaints/", headers=env["other_h"], data={
        "product_id": str(env["ids"]["product"]), "title": "Real", "description": "Insects inside the packet"})
    real_cid = real.json()["complaint_id"]
    resolve_as(env, test_cid, "Packaging Defect", "Poor Sealing")
    resolve_as(env, real_cid, "Infestation", "Insect Presence")
    live, tst, everything = monitoring(env), monitoring(env, scope="test"), monitoring(env, scope="all")
    assert live["basis"]["verified_incidents"] == 1 and "real customer complaints only" in live["basis"]["statement"]
    assert tst["basis"]["verified_incidents"] == 1 and "NOT real-world" in tst["basis"]["statement"]
    assert everything["basis"]["verified_incidents"] == 2 and "NOT real-world" in everything["basis"]["statement"]
    assert monitoring(env, scope="imported")["basis"]["verified_incidents"] == 0   # imports have no verified incidents


def test_undetermined_predictions_are_not_counted_as_wrong(env, monkeypatch):
    # Force the "no reliable prediction" branch (no LLM, no symptom rule, weak ML guess).
    monkeypatch.setattr(settings, "ML_CONFIDENCE_THRESHOLD", 1.01)
    monkeypatch.setattr(settings, "ML_MIN_GUESS_CONFIDENCE", 1.01)
    cid = submit(env, "Odd", "qwerty asdf zxcv")
    resolve_as(env, cid, "Other Customer Concern", "Other")
    m = monitoring(env)
    assert m["basis"]["verified_incidents"] == 1 and m["basis"]["predictions_assessed"] == 0
    assert m["accuracy"]["category"]["value_pct"] is None and m["accuracy"]["coverage_pct"] == 0.0
    assert m["unfamiliar"]["undetermined_verified"] == 1


def test_new_issue_types_and_llm_proposals_are_surfaced(env):
    cid = submit(env, "Printing", "The QR code on every carton scans to a 404 page")
    resolve_as(env, cid, "Other / New Issue", "QR Code Failure")
    db = env["Session"]()
    try:
        pk = db.query(Complaint.id).filter(Complaint.complaint_id == cid).scalar()
        a = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == pk).first()
        a.prediction_source = "llm"
        a.llm_result = {"category": "Other / New Issue", "subcategory": "QR Code Failure", "provider": "groq"}
        db.commit()
    finally:
        db.close()
    m = monitoring(env)
    assert {"label": "QR Code Failure", "count": 1} in m["unfamiliar"]["verified_new_issue_types"]
    assert {"label": "QR Code Failure", "count": 1} in m["unfamiliar"]["llm_proposed_unknown_subcategories"]
    assert m["pipeline"]["llm_providers"] == {"groq": 1}


def test_report_is_generated_from_the_same_numbers_and_is_admin_only(env):
    cid = submit(env, "Seal", "Pack seal was open when I bought it")
    resolve_as(env, cid, "Packaging Defect", "Poor Sealing")
    res = env["client"].get(MON + "/report", headers=env["admin_h"])
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/markdown")
    text = res.text
    assert "scope **live**" in text and "real customer complaints only" in text
    assert "Category accuracy: **100.0%**" in text and "UNRELIABLE" in text       # n=1 flagged, not hidden
    assert "never triggers promotion" in text
    assert env["client"].get(MON, headers=env["cust_h"]).status_code == 403
    assert env["client"].get(MON, headers=env["admin_h"], params={"scope": "bogus"}).status_code == 422


def test_monitoring_never_modifies_data_or_models(env):
    from app.intelligence import classifier
    before = classifier.load_active().version
    cid = submit(env, "Seal", "Pack seal was open when I bought it")
    resolve_as(env, cid, "Packaging Defect", "Poor Sealing")
    monitoring(env)
    env["client"].get(MON + "/report", headers=env["admin_h"])
    assert classifier.load_active().version == before
    db = env["Session"]()
    try:
        assert db.query(IncidentResolution).filter(IncidentResolution.used_in_training_run.isnot(None)).count() == 0
    finally:
        db.close()
