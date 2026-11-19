"""
Issue-management, AI-performance and business-impact analytics.

Every figure is computed from database rows. Impact figures that need a money
value (cost saved) are only reported when the operator configures the unit
cost assumptions; otherwise they are returned as null with an explanation.
"""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence.classifier import load_active

REPEAT_WINDOW_DAYS = 90
YEARLY_GRANULARITY_MONTHS = 36


def _frame(db: Session, sql: str, params: Optional[dict] = None, dates=()) -> pd.DataFrame:
    rows = db.execute(sql_text(sql), params or {}).fetchall()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    for col in dates:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _complaints(db: Session) -> pd.DataFrame:
    return _frame(db, "SELECT id, complaint_id, record_type, status, category, complaint_subcategory AS sub, "
                      "product_id, units_affected, submitted_date, resolved_date FROM complaints",
                  dates=("submitted_date", "resolved_date"))


def _window(df: pd.DataFrame, start: Optional[datetime], end: Optional[datetime]):
    if df.empty:
        now = datetime.utcnow()
        return start or now, end or now
    lo = start or df["submitted_date"].min().to_pydatetime()
    # Open-ended window runs to "now" so resolutions/feedback recorded after the
    # latest submission are included.
    hi = end or max(df["submitted_date"].max().to_pydatetime(), datetime.utcnow())
    return lo, hi


def _pct(num, den) -> Optional[float]:
    return round(100.0 * num / den, 2) if den else None


def _change(current, prior) -> Optional[float]:
    if current is None or prior in (None, 0):
        return None
    return round(100.0 * (current - prior) / prior, 2)


def _repeat_rate(all_df: pd.DataFrame, lo, hi) -> Optional[float]:
    df = all_df.dropna(subset=["submitted_date", "product_id", "sub"]).sort_values("submitted_date")
    if df.empty:
        return None
    df = df.assign(prev=df.groupby(["product_id", "sub"])["submitted_date"].shift(1))
    in_win = df[(df["submitted_date"] >= lo) & (df["submitted_date"] <= hi)]
    if in_win.empty:
        return None
    repeat = (in_win["submitted_date"] - in_win["prev"]).dt.days <= REPEAT_WINDOW_DAYS
    return round(100.0 * repeat.sum() / len(in_win), 2)


def _issue_block(df: pd.DataFrame) -> dict:
    total = len(df)
    resolved = df[df["status"] == "resolved"]
    pending = df[~df["status"].isin(["resolved", "rejected"])]
    durations = (resolved["resolved_date"] - resolved["submitted_date"]).dt.total_seconds() / 86400
    # Imported historical rows carry resolved_date == submitted_date (duration not recorded);
    # only rows with a recorded, positive duration count toward resolution time.
    durations = durations[durations > 0]
    return {
        "total_queries": total,
        "issues_identified": int(df["category"].notna().sum()),
        "issues_resolved": len(resolved),
        "pending_issues": len(pending),
        "avg_resolution_days": round(float(durations.mean()), 4) if len(durations) else None,
        "resolution_time_sample": int(len(durations)),
        "resolution_rate_pct": _pct(len(resolved), total),
    }


def compute_kpis(db: Session, start: Optional[datetime] = None, end: Optional[datetime] = None,
                 category: Optional[str] = None) -> dict:
    all_c = _complaints(db)
    lo, hi = _window(all_c, start, end)
    span = hi - lo
    prior_lo, prior_hi = lo - span - timedelta(days=1), lo - timedelta(days=1)
    base = all_c if not category or all_c.empty else all_c[all_c["category"] == category]

    def in_range(df, a, b, col="submitted_date"):
        return df[(df[col] >= a) & (df[col] <= b)] if not df.empty else df

    cur = in_range(base, lo, hi)
    prior = in_range(base, prior_lo, prior_hi)
    issues = _issue_block(cur) if not cur.empty else _issue_block(pd.DataFrame(columns=all_c.columns))
    prior_issues = _issue_block(prior) if not prior.empty else None
    issues["avg_resolution_days_change_pct"] = _change(
        issues["avg_resolution_days"], prior_issues and prior_issues["avg_resolution_days"])

    params = {"lo": lo, "hi": hi}
    cat_sql = " AND COALESCE(r.verified_category, a.predicted_category) = :cat" if category else ""
    if category:
        params["cat"] = category
    analyses = _frame(db, "SELECT a.prediction_source, a.is_low_confidence, a.predicted_category, a.created_at "
                          "FROM issue_analyses a LEFT JOIN incident_resolutions r ON r.complaint_id = a.complaint_id "
                          f"WHERE a.created_at BETWEEN :lo AND :hi{cat_sql}", params)
    res_cat = " AND r.verified_category = :cat" if category else ""
    resolutions = _frame(db, "SELECT r.category_correct, r.root_cause_correct, r.units_contained, "
                             "r.downtime_avoided_hours, c.units_affected FROM incident_resolutions r "
                             f"JOIN complaints c ON c.id = r.complaint_id WHERE r.resolved_at BETWEEN :lo AND :hi{res_cat}",
                         params)
    feedback = _frame(db, "SELECT f.rating, f.satisfied FROM resolution_feedback f "
                          "WHERE f.created_at BETWEEN :lo AND :hi", {"lo": lo, "hi": hi})

    n_an = len(analyses)
    src = analyses["prediction_source"].value_counts().to_dict() if n_an else {}
    judged = resolutions["category_correct"].dropna() if len(resolutions) else pd.Series(dtype=bool)
    correct = int(judged.astype(bool).sum()) if len(judged) else 0
    model = load_active()
    ai = {
        "predictions_total": n_an,
        "ml_prediction_count": int(src.get("ml", 0)),
        "llm_fallback_count": int(src.get("llm", 0)),
        "rules_fallback_count": int(src.get("rules", 0)),
        "low_confidence_count": int(analyses["is_low_confidence"].astype(bool).sum()) if n_an else 0,
        "verified_predictions": len(judged),
        "prediction_accuracy_pct": _pct(correct, len(judged)),
        "admin_correction_rate_pct": _pct(len(judged) - correct, len(judged)),
        "top_predicted_categories": (analyses["predicted_category"].value_counts().head(5)
                                     .rename_axis("category").reset_index(name="count")
                                     .to_dict("records") if n_an else []),
        "offline_benchmark_accuracy_pct": (
            round(100 * model.metadata["metrics"]["benchmark_accuracy"], 2)
            if model and model.metadata.get("metrics") else None),
    }

    units = int(resolutions["units_contained"].fillna(0).sum()) if len(resolutions) else 0
    affected = int(resolutions["units_affected"].fillna(0).sum()) if len(resolutions) else 0
    downtime = float(resolutions["downtime_avoided_hours"].fillna(0).sum()) if len(resolutions) else 0.0
    cost = None
    if settings.IMPACT_UNIT_COST_INR is not None or settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR is not None:
        cost = round(units * (settings.IMPACT_UNIT_COST_INR or 0)
                     + downtime * (settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR or 0), 2)
    rep_now = _repeat_rate(base, lo, hi) if not base.empty else None
    rep_prior = _repeat_rate(base, prior_lo, prior_hi) if not base.empty else None
    n_fb = len(feedback)
    impact = {
        "products_saved_units": units,
        "wastage_reduction_pct": _pct(units, units + affected),
        "estimated_cost_saved_inr": cost,
        "downtime_avoided_hours": round(downtime, 2),
        "customer_satisfaction_pct": _pct(int(feedback["satisfied"].astype(bool).sum()), n_fb) if n_fb else None,
        "avg_rating": round(float(feedback["rating"].mean()), 2) if n_fb else None,
        "feedback_count": n_fb,
        "repeat_incident_rate_pct": rep_now,
        "repeat_incident_rate_prior_pct": rep_prior,
        "repeat_incident_reduction_pct": (round(100 * (rep_prior - rep_now) / rep_prior, 2)
                                          if rep_now is not None and rep_prior else None),
    }
    return {
        "window": {"start": lo.isoformat(), "end": hi.isoformat(),
                   "prior_start": prior_lo.isoformat(), "prior_end": prior_hi.isoformat(),
                   "category": category},
        "issue_management": issues,
        "ai_performance": ai,
        "business_impact": impact,
        "assumptions": assumptions(),
    }


def assumptions() -> list:
    unit = settings.IMPACT_UNIT_COST_INR
    hour = settings.IMPACT_DOWNTIME_COST_PER_HOUR_INR
    return [
        {"metric": "Products saved", "definition": "Sum of units the admin recorded as contained / quarantined "
         "before reaching customers when resolving an incident. Never inferred."},
        {"metric": "Wastage reduction %", "definition": "Units contained ÷ (units contained + units the customer "
         "reported as affected) across incidents resolved in the window."},
        {"metric": "Cost saved", "definition": (
            f"Units contained × ₹{unit}/unit + downtime avoided × ₹{hour}/hour." if unit or hour else
            "Not reported: set IMPACT_UNIT_COST_INR and/or IMPACT_DOWNTIME_COST_PER_HOUR_INR.")},
        {"metric": "Average resolution time", "definition": "Mean days from submission to resolution over "
         "complaints with a recorded duration. Imported historical records whose resolution date equals the "
         "submission date (duration not captured) are excluded; the sample size is shown."},
        {"metric": "Downtime avoided", "definition": "Sum of hours the admin estimated as avoided at resolution."},
        {"metric": "Customer satisfaction %", "definition": "Share of customer ratings marked satisfied "
         "(rating ≥ 4) on resolved incidents."},
        {"metric": "Repeat incident rate", "definition": f"Share of complaints with an earlier complaint for the same "
         f"product and subcategory within {REPEAT_WINDOW_DAYS} days; reduction compares with the prior window of "
         "equal length."},
        {"metric": "Prediction accuracy", "definition": "Admin-verified incidents whose AI-predicted category matched "
         "the verified category. The offline benchmark figure is a small independent test set, shown separately."},
    ]


def compute_trends(db: Session, start: Optional[datetime] = None, end: Optional[datetime] = None,
                   category: Optional[str] = None) -> dict:
    all_c = _complaints(db)
    lo, hi = _window(all_c, start, end)
    months = (hi.year - lo.year) * 12 + hi.month - lo.month
    freq, fmt = ("Y", "%Y") if months > YEARLY_GRANULARITY_MONTHS else ("M", "%Y-%m")
    df = all_c if not category or all_c.empty else all_c[all_c["category"] == category]
    received = df[(df["submitted_date"] >= lo) & (df["submitted_date"] <= hi)] if not df.empty else df
    resolved = df[(df["resolved_date"] >= lo) & (df["resolved_date"] <= hi)] if not df.empty else df

    def bucket(series):
        return series.dt.strftime(fmt)

    periods = {}
    if not received.empty:
        for p, n in bucket(received["submitted_date"]).value_counts().items():
            periods.setdefault(p, {"period": p, "received": 0, "resolved": 0})["received"] = int(n)
    if not resolved.empty:
        res = resolved.assign(days=(resolved["resolved_date"] - resolved["submitted_date"]).dt.total_seconds() / 86400,
                              period=bucket(resolved["resolved_date"]))
        for p, g in res.groupby("period"):
            row = periods.setdefault(p, {"period": p, "received": 0, "resolved": 0})
            row["resolved"] = len(g)
            recorded = g["days"][g["days"] > 0]
            row["avg_resolution_days"] = round(float(recorded.mean()), 2) if len(recorded) else None

    params = {"lo": lo, "hi": hi}
    ai = _frame(db, "SELECT a.created_at, a.prediction_source, r.category_correct FROM issue_analyses a "
                    "LEFT JOIN incident_resolutions r ON r.complaint_id = a.complaint_id "
                    "WHERE a.created_at BETWEEN :lo AND :hi", params, dates=("created_at",))
    ai_rows = []
    if not ai.empty:
        ai = ai.assign(period=bucket(ai["created_at"]))
        for p, g in ai.groupby("period"):
            judged = g["category_correct"].dropna()
            ai_rows.append({"period": p, "ml": int((g["prediction_source"] == "ml").sum()),
                            "llm": int((g["prediction_source"] == "llm").sum()),
                            "rules": int((g["prediction_source"] == "rules").sum()),
                            "accuracy_pct": _pct(int(judged.astype(bool).sum()), len(judged))})
    sat = _frame(db, "SELECT f.created_at, f.satisfied FROM resolution_feedback f "
                     "WHERE f.created_at BETWEEN :lo AND :hi", params, dates=("created_at",))
    sat_rows = []
    if not sat.empty:
        sat = sat.assign(period=bucket(sat["created_at"]))
        sat_rows = [{"period": p, "satisfaction_pct": _pct(int(g["satisfied"].astype(bool).sum()), len(g)),
                     "responses": len(g)} for p, g in sat.groupby("period")]
    wastage = _frame(db, "SELECT r.resolved_at, r.units_contained FROM incident_resolutions r "
                         "WHERE r.resolved_at BETWEEN :lo AND :hi", params, dates=("resolved_at",))
    wastage_rows = []
    if not wastage.empty:
        wastage = wastage.assign(period=bucket(wastage["resolved_at"]))
        wastage_rows = [{"period": p, "units_contained": int(g["units_contained"].fillna(0).sum())}
                        for p, g in wastage.groupby("period")]
    cats = (received["category"].value_counts().head(10).rename_axis("category").reset_index(name="count")
            .to_dict("records") if not received.empty else [])
    return {
        "granularity": "year" if freq == "Y" else "month",
        "issues": sorted(periods.values(), key=lambda r: r["period"]),
        "category_distribution": cats,
        "ai_performance": ai_rows,
        "customer_satisfaction": sat_rows,
        "wastage": wastage_rows,
    }
