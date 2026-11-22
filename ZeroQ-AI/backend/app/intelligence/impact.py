"""
Issue-management, AI-performance and business-impact analytics.

Rules (enforced here and covered by tests/test_analytics.py):
  * Data scope is explicit. "live" (default) = complaints submitted on the platform;
    "imported" = the historical/synthetic dataset (identified by `customer_id`, which
    only the import sets); "all" = both. Synthetic data is never presented as live.
  * Every figure is computed from rows; when the inputs do not exist the value is
    None (shown as N/A), never a default or an estimate in disguise.
  * Each business metric carries its basis: admin_reported, admin_estimate,
    customer_reported, computed, or estimate (assumption-based).
"""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence.classifier import load_active
from app.intelligence.origin import ORIGIN_SQL

REPEAT_WINDOW_DAYS = 90
REPEAT_MIN_SAMPLE = 30          # complaints per window needed before a repeat-rate comparison is shown
YEARLY_GRANULARITY_MONTHS = 36
SCOPES = ORIGIN_SQL   # live | test | imported | all  (see origin.py)
METRIC_BASIS = {
    "products_saved_units": "admin_reported",
    "wastage_reduction_pct": "admin_reported",
    "estimated_cost_saved_inr": "estimate",
    "downtime_avoided_hours": "admin_estimate",
    "customer_satisfaction_pct": "customer_reported",
    "repeat_incident_reduction_pct": "computed",
}


def _frame(db: Session, sql: str, params: Optional[dict] = None, dates=()) -> pd.DataFrame:
    rows = db.execute(sql_text(sql), params or {}).fetchall()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    for col in dates:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _scope_clause(scope: str) -> str:
    """Constant SQL fragment for a validated scope key; never user text."""
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    return SCOPES[scope]


def _complaints(db: Session, scope: str) -> pd.DataFrame:
    df = _frame(db, "SELECT c.id, c.status, c.category, c.complaint_subcategory AS sub, c.product_id, "
                    f"c.submitted_date, c.resolved_date FROM complaints c WHERE {_scope_clause(scope)}",  # nosec B608 - constant fragment
                dates=("submitted_date", "resolved_date"))
    if df.empty:
        df = pd.DataFrame(columns=["id", "status", "category", "sub", "product_id", "submitted_date", "resolved_date"])
        df["submitted_date"] = pd.to_datetime(df["submitted_date"])
        df["resolved_date"] = pd.to_datetime(df["resolved_date"])
    return df


def _window(df: pd.DataFrame, start: Optional[datetime], end: Optional[datetime]):
    now = datetime.utcnow()
    first = df["submitted_date"].min() if not df.empty else None
    lo = start or (first.to_pydatetime() if first is not None and not pd.isna(first) else now - timedelta(days=1))
    # Open-ended windows run to "now" so resolutions/feedback after the latest submission count.
    last = df["submitted_date"].max() if not df.empty else None
    hi = end or max(last.to_pydatetime() if last is not None and not pd.isna(last) else now, now)
    return lo, hi


def _pct(num, den) -> Optional[float]:
    return round(100.0 * num / den, 2) if den else None


def _change(current, prior) -> Optional[float]:
    if current is None or prior in (None, 0):
        return None
    return round(100.0 * (current - prior) / prior, 2)


def _in(df: pd.DataFrame, col: str, lo, hi) -> pd.DataFrame:
    return df[(df[col] >= lo) & (df[col] <= hi)] if not df.empty else df


def _repeat_rate(df_all: pd.DataFrame, lo, hi) -> tuple:
    """(rate %, sample size). A complaint repeats if the same product+subcategory had a
    complaint within REPEAT_WINDOW_DAYS before it."""
    df = df_all.dropna(subset=["submitted_date", "product_id", "sub"]).sort_values("submitted_date")
    if df.empty:
        return None, 0
    df = df.assign(prev=df.groupby(["product_id", "sub"])["submitted_date"].shift(1))
    in_win = _in(df, "submitted_date", lo, hi)
    if in_win.empty:
        return None, 0
    repeat = (in_win["submitted_date"] - in_win["prev"]).dt.days <= REPEAT_WINDOW_DAYS
    return round(100.0 * repeat.sum() / len(in_win), 2), len(in_win)


def _issue_block(df: pd.DataFrame) -> dict:
    total = len(df)
    resolved = df[df["status"] == "resolved"]
    pending = df[~df["status"].isin(["resolved", "rejected"])]
    durations = (resolved["resolved_date"] - resolved["submitted_date"]).dt.total_seconds() / 86400
    # Imported rows carry resolved_date == submitted_date (duration never recorded): only a
    # recorded, positive duration counts toward resolution time.
    durations = durations[durations > 0]
    return {
        "total_queries": total,
        "issues_identified": int(df["category"].notna().sum()) if total else 0,
        "issues_resolved": len(resolved),
        "pending_issues": len(pending),
        "avg_resolution_days": round(float(durations.mean()), 4) if len(durations) else None,
        "resolution_time_sample": int(len(durations)),
        "resolution_rate_pct": _pct(len(resolved), total),
    }


def _scoped_rows(db: Session, scope: str, lo, hi, category: Optional[str]):
    params = {"lo": lo, "hi": hi, "cat": category}
    where = _scope_clause(scope)   # constant fragment; all values are bound parameters
    analyses = _frame(db, "SELECT a.prediction_source, a.is_low_confidence, a.predicted_category, a.created_at, "
                          "r.category_correct FROM issue_analyses a JOIN complaints c ON c.id = a.complaint_id "
                          "LEFT JOIN incident_resolutions r ON r.complaint_id = a.complaint_id "
                          f"WHERE {where} AND a.created_at BETWEEN :lo AND :hi "  # nosec B608
                          "AND (:cat IS NULL OR COALESCE(r.verified_category, a.predicted_category) = :cat)",
                      params, dates=("created_at",))
    resolutions = _frame(db, "SELECT r.category_correct, r.units_contained, r.units_at_risk, "
                             "r.downtime_avoided_hours, r.resolved_at FROM incident_resolutions r "
                             f"JOIN complaints c ON c.id = r.complaint_id WHERE {where} "  # nosec B608
                             "AND r.resolved_at BETWEEN :lo AND :hi AND (:cat IS NULL OR r.verified_category = :cat)",
                         params, dates=("resolved_at",))
    feedback = _frame(db, "SELECT f.rating, f.satisfied, f.created_at FROM resolution_feedback f "
                          "JOIN complaints c ON c.id = f.complaint_id "
                          "LEFT JOIN incident_resolutions r ON r.complaint_id = f.complaint_id "
                          f"WHERE {where} AND f.created_at BETWEEN :lo AND :hi "  # nosec B608
                          "AND (:cat IS NULL OR COALESCE(r.verified_category, c.category) = :cat)",
                      params, dates=("created_at",))
    return analyses, resolutions, feedback


def _ai_block(analyses: pd.DataFrame) -> dict:
    n = len(analyses)
    src = analyses["prediction_source"].value_counts().to_dict() if n else {}
    judged = analyses["category_correct"].dropna() if n else pd.Series(dtype=bool)
    correct = int(judged.astype(bool).sum()) if len(judged) else 0
    model = load_active()
    metrics = (model.metadata.get("metrics") or {}) if model else {}
    return {
        "predictions_total": n,
        "ml_prediction_count": int(src.get("ml", 0)),
        "llm_fallback_count": int(src.get("llm", 0)),
        "rules_fallback_count": int(src.get("rules", 0)),
        "undetermined_count": int(src.get("undetermined", 0)),
        "low_confidence_count": int(analyses["is_low_confidence"].astype(bool).sum()) if n else 0,
        "verified_predictions": len(judged),
        "prediction_accuracy_pct": _pct(correct, len(judged)),
        "admin_correction_rate_pct": _pct(len(judged) - correct, len(judged)),
        "top_predicted_categories": (analyses["predicted_category"].dropna().value_counts().head(5)
                                     .rename_axis("category").reset_index(name="count").to_dict("records")
                                     if n else []),
        "offline_benchmark_accuracy_pct": (round(100 * metrics["benchmark_accuracy"], 2)
                                           if metrics.get("benchmark_accuracy") is not None else None),
        "offline_benchmark_n": metrics.get("benchmark_n"),
    }


def _impact_block(resolutions: pd.DataFrame, feedback: pd.DataFrame, base: pd.DataFrame,
                  lo, hi, prior_lo, prior_hi) -> dict:
    has = len(resolutions) > 0
    if has:  # nullable integer columns arrive as object dtype when all-null
        resolutions = resolutions.assign(**{c: pd.to_numeric(resolutions[c], errors="coerce")
                                            for c in ("units_contained", "units_at_risk", "downtime_avoided_hours")})
    units = int(resolutions["units_contained"].fillna(0).sum()) if has else 0
    downtime = float(resolutions["downtime_avoided_hours"].fillna(0).sum()) if has else 0.0
    at_risk_rows = resolutions[resolutions["units_at_risk"].fillna(0) > 0] if has else resolutions
    at_risk = int(at_risk_rows["units_at_risk"].sum()) if len(at_risk_rows) else 0
    contained_with_risk = int(at_risk_rows["units_contained"].fillna(0).sum()) if len(at_risk_rows) else 0
    cost = None
    if has and (settings.IMPACT_UNIT_COST_INR is not None or settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR is not None):
        cost = round(units * (settings.IMPACT_UNIT_COST_INR or 0)
                     + downtime * (settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR or 0), 2)
    rep_now, n_now = _repeat_rate(base, lo, hi)
    rep_prior, n_prior = _repeat_rate(base, prior_lo, prior_hi)
    enough = n_now >= REPEAT_MIN_SAMPLE and n_prior >= REPEAT_MIN_SAMPLE
    n_fb = len(feedback)
    return {
        "products_saved_units": units,
        "wastage_reduction_pct": _pct(contained_with_risk, at_risk) if at_risk else None,
        "wastage_sample": len(at_risk_rows),
        "estimated_cost_saved_inr": cost,
        "downtime_avoided_hours": round(downtime, 2),
        "customer_satisfaction_pct": _pct(int(feedback["satisfied"].astype(bool).sum()), n_fb) if n_fb else None,
        "avg_rating": round(float(feedback["rating"].mean()), 2) if n_fb else None,
        "feedback_count": n_fb,
        "repeat_incident_rate_pct": rep_now if n_now >= REPEAT_MIN_SAMPLE else None,
        "repeat_incident_rate_prior_pct": rep_prior if n_prior >= REPEAT_MIN_SAMPLE else None,
        "repeat_incident_reduction_pct": (round(100 * (rep_prior - rep_now) / rep_prior, 2)
                                          if enough and rep_prior else None),
        "repeat_sample": {"current": n_now, "prior": n_prior, "minimum": REPEAT_MIN_SAMPLE},
        "metric_basis": METRIC_BASIS,
    }


def compute_kpis(db: Session, start: Optional[datetime] = None, end: Optional[datetime] = None,
                 category: Optional[str] = None, scope: str = "live") -> dict:
    all_c = _complaints(db, scope)
    lo, hi = _window(all_c, start, end)
    span = hi - lo
    prior_lo, prior_hi = lo - span - timedelta(days=1), lo - timedelta(days=1)
    base = all_c if not category else all_c[all_c["category"] == category]

    cur = _in(base, "submitted_date", lo, hi)
    prior = _in(base, "submitted_date", prior_lo, prior_hi)
    issues = _issue_block(cur)
    prior_issues = _issue_block(prior) if len(prior) else None
    issues["avg_resolution_days_change_pct"] = _change(
        issues["avg_resolution_days"], prior_issues and prior_issues["avg_resolution_days"])

    analyses, resolutions, feedback = _scoped_rows(db, scope, lo, hi, category)
    return {
        "window": {"start": lo.isoformat(), "end": hi.isoformat(), "prior_start": prior_lo.isoformat(),
                   "prior_end": prior_hi.isoformat(), "category": category, "scope": scope},
        "issue_management": issues,
        "ai_performance": _ai_block(analyses),
        "business_impact": _impact_block(resolutions, feedback, base, lo, hi, prior_lo, prior_hi),
        "assumptions": assumptions(),
    }


def assumptions() -> list:
    unit = settings.IMPACT_UNIT_COST_INR
    hour = settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR
    return [
        {"metric": "Data scope", "definition": "Live = complaints from real customers submitted on the platform "
         "(default). Test = submissions from designated test/demo accounts. Imported = the historical/synthetic "
         "dataset loaded at setup (rows carrying a dataset customer_id). Scopes are never mixed unless 'all' is chosen."},
        {"metric": "Products saved", "definition": "Sum of units the admin recorded as contained / quarantined "
         "when resolving an incident (admin-reported). Never inferred."},
        {"metric": "Wastage reduction %", "definition": "Units contained ÷ units at risk, over resolutions where "
         "the admin recorded units at risk. N/A when no at-risk figure has been recorded."},
        {"metric": "Cost saved", "definition": (
            f"Estimate: units contained × ₹{unit}/unit + downtime avoided × ₹{hour}/hour." if unit or hour else
            "Not reported: set IMPACT_UNIT_COST_INR and/or IMPACT_DOWNTIME_COST_PER_HOUR_INR.")},
        {"metric": "Downtime avoided", "definition": "Sum of hours the admin estimated as avoided at resolution."},
        {"metric": "Average resolution time", "definition": "Mean time from submission to resolution over "
         "complaints with a recorded, positive duration; the sample size is shown."},
        {"metric": "Customer satisfaction %", "definition": "Share of submitted customer ratings that are ≥ 4/5. "
         "N/A until at least one rating exists."},
        {"metric": "Repeat incident rate", "definition": f"Share of complaints preceded by another complaint for the "
         f"same product and subcategory within {REPEAT_WINDOW_DAYS} days; the reduction compares with the prior "
         f"window of equal length and is shown only when both windows have ≥ {REPEAT_MIN_SAMPLE} complaints."},
        {"metric": "Prediction accuracy", "definition": "Admin-verified incidents whose AI-predicted category matched "
         "the verified category. The offline benchmark is a small independent test set, shown separately."},
    ]


def compute_trends(db: Session, start: Optional[datetime] = None, end: Optional[datetime] = None,
                   category: Optional[str] = None, scope: str = "live") -> dict:
    all_c = _complaints(db, scope)
    lo, hi = _window(all_c, start, end)
    months = (hi.year - lo.year) * 12 + hi.month - lo.month
    granularity, fmt = ("year", "%Y") if months > YEARLY_GRANULARITY_MONTHS else ("month", "%Y-%m")
    df = all_c if not category else all_c[all_c["category"] == category]
    received = _in(df, "submitted_date", lo, hi)
    resolved = df[(df["resolved_date"] >= lo) & (df["resolved_date"] <= hi)] if not df.empty else df

    periods = {}
    if len(received):
        for p, n in received["submitted_date"].dt.strftime(fmt).value_counts().items():
            periods.setdefault(p, {"period": p, "received": 0, "resolved": 0})["received"] = int(n)
    if len(resolved):
        res = resolved.assign(days=(resolved["resolved_date"] - resolved["submitted_date"]).dt.total_seconds() / 86400,
                              period=resolved["resolved_date"].dt.strftime(fmt))
        for p, g in res.groupby("period"):
            row = periods.setdefault(p, {"period": p, "received": 0, "resolved": 0})
            row["resolved"] = len(g)
            recorded = g["days"][g["days"] > 0]
            row["avg_resolution_days"] = round(float(recorded.mean()), 4) if len(recorded) else None

    analyses, resolutions, feedback = _scoped_rows(db, scope, lo, hi, category)
    ai_rows = []
    if len(analyses):
        analyses = analyses.assign(period=analyses["created_at"].dt.strftime(fmt))
        for p, g in analyses.groupby("period"):
            judged = g["category_correct"].dropna()
            ai_rows.append({"period": p, **{s: int((g["prediction_source"] == s).sum())
                                             for s in ("ml", "llm", "rules", "undetermined")},
                            "accuracy_pct": _pct(int(judged.astype(bool).sum()), len(judged))})
    sat_rows = []
    if len(feedback):
        feedback = feedback.assign(period=feedback["created_at"].dt.strftime(fmt))
        sat_rows = [{"period": p, "satisfaction_pct": _pct(int(g["satisfied"].astype(bool).sum()), len(g)),
                     "responses": len(g)} for p, g in feedback.groupby("period")]
    wastage_rows = []
    if len(resolutions):
        resolutions = resolutions.assign(period=resolutions["resolved_at"].dt.strftime(fmt))
        wastage_rows = [{"period": p, "units_contained": int(g["units_contained"].fillna(0).sum())}
                        for p, g in resolutions.groupby("period") if g["units_contained"].fillna(0).sum() > 0]
    cats = (received["category"].dropna().value_counts().head(10).rename_axis("category")
            .reset_index(name="count").to_dict("records") if len(received) else [])
    return {
        "scope": scope,
        "granularity": granularity,
        "issues": sorted(periods.values(), key=lambda r: r["period"]),
        "category_distribution": cats,
        "ai_performance": ai_rows,
        "customer_satisfaction": sat_rows,
        "wastage": wastage_rows,
    }
