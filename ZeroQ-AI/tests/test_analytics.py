"""Analytics correctness (C3, H4, M6): data scope, valid timestamps, no fabricated metrics, filter consistency."""
from conftest import submit

KPI = "/api/admin/intelligence/kpis"
TRENDS = "/api/admin/intelligence/trends"
RESOLVE = "/api/admin/intelligence/incidents/{}/resolve"


def kpis(env, **params):
    res = env["client"].get(KPI, headers=env["admin_h"], params=params)
    assert res.status_code == 200, res.text
    return res.json()


def test_default_scope_is_live_platform_data_only(env):
    body = kpis(env)
    assert body["window"]["scope"] == "live"
    # The fixture holds 28 imported (synthetic) resolved complaints and no live ones yet.
    assert body["issue_management"]["total_queries"] == 0
    assert body["issue_management"]["issues_resolved"] == 0
    imported = kpis(env, scope="imported")["issue_management"]
    assert imported["total_queries"] == 28 and imported["issues_resolved"] == 28


def test_unavailable_metrics_are_null_not_invented(env):
    bi = kpis(env)["business_impact"]
    assert bi["customer_satisfaction_pct"] is None
    assert bi["wastage_reduction_pct"] is None
    assert bi["estimated_cost_saved_inr"] is None
    assert bi["repeat_incident_reduction_pct"] is None
    ai = kpis(env)["ai_performance"]
    assert ai["prediction_accuracy_pct"] is None


def test_resolution_time_uses_valid_timestamps(env):
    # Imported fixture rows resolve 5 days after submission.
    assert kpis(env, scope="imported")["issue_management"]["avg_resolution_days"] == 5.0


def test_unresolved_live_complaints_are_pending_not_resolved(env):
    submit(env, "Open one", "Leaking pouch")
    submit(env, "Open two", "Insects inside the packet")
    im = kpis(env)["issue_management"]
    assert im["total_queries"] == 2
    assert im["issues_resolved"] == 0 and im["pending_issues"] == 2
    assert im["resolution_rate_pct"] == 0.0


def test_wastage_requires_recorded_units_at_risk(env):
    client = env["client"]
    cid = submit(env, "Seal", "Pack seal was open")
    body = {"verified_category": "Packaging Defect", "confirmed_root_cause": "Seal jaw worn",
            "resolution_action": "Replaced seal jaw", "admin_explanation": "We replaced a worn part.",
            "units_contained": 40}
    bad = client.post(RESOLVE.format(cid), headers=env["admin_h"], json={**body, "units_at_risk": 10})
    assert bad.status_code == 422                       # contained cannot exceed at-risk
    ok = client.post(RESOLVE.format(cid), headers=env["admin_h"], json={**body, "units_at_risk": 200})
    assert ok.status_code == 200, ok.text
    bi = kpis(env)["business_impact"]
    assert bi["products_saved_units"] == 40
    assert bi["wastage_reduction_pct"] == 20.0
    assert bi["metric_basis"]["products_saved_units"] == "admin_reported"
    assert bi["metric_basis"]["estimated_cost_saved_inr"] == "estimate"


def test_satisfaction_comes_only_from_submitted_feedback(env):
    client = env["client"]
    cid = submit(env, "Seal 2", "Pack seal was open")
    client.post(RESOLVE.format(cid), headers=env["admin_h"], json={
        "verified_category": "Packaging Defect", "confirmed_root_cause": "Seal jaw worn",
        "resolution_action": "Replaced seal jaw", "admin_explanation": "We replaced a worn part."})
    assert kpis(env)["business_impact"]["customer_satisfaction_pct"] is None
    assert client.post(f"/api/complaints/{cid}/feedback", headers=env["cust_h"], json={"rating": 2}).status_code == 200
    bi = kpis(env)["business_impact"]
    assert bi["customer_satisfaction_pct"] == 0.0 and bi["feedback_count"] == 1


def test_category_filter_applies_to_every_trend_series(env):
    t = env["client"].get(TRENDS, headers=env["admin_h"], params={"category": "Infestation"}).json()
    assert all(c["category"] == "Infestation" for c in t["category_distribution"])
    total_ai = sum(r["ml"] + r["llm"] + r["rules"] + r.get("undetermined", 0) for r in t["ai_performance"])
    assert total_ai == 1                                 # only the insect complaint
    assert t["wastage"] == []                            # the resolved incidents were Packaging Defect
    k = kpis(env, category="Infestation")
    assert k["ai_performance"]["predictions_total"] == 1
    assert k["business_impact"]["products_saved_units"] == 0


def test_invalid_scope_is_rejected(env):
    assert env["client"].get(KPI, headers=env["admin_h"], params={"scope": "everything"}).status_code == 422
