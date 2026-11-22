"""
Real-world model monitoring.

Basis: admin-verified incidents on REAL customer complaints (scope "live" by default). Synthetic
imports are never included unless the caller explicitly asks for another scope, and the scope is
echoed in the result. Nothing is estimated: when there is not enough data a metric carries
`reliable: false`, a confidence interval, and the sample size — or is null.

Ground truth  = IncidentResolution.verified_category (set by an administrator).
Predictions   = IssueAnalysis (final prediction + the ML and LLM sub-results kept for comparison).
"""
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence.evaluation import calibration_report, classification_report, wilson_interval
from app.intelligence.origin import complaint_origin
from app.intelligence.taxonomy import NEW_ISSUE_CATEGORY, SUBCATEGORY_TO_CATEGORY
from app.models.complaint import Complaint
from app.models.intelligence import IncidentResolution, IssueAnalysis

MIN_VERIFIED_FOR_RATES = 30      # below this, headline rates are flagged unreliable
MIN_PER_GROUP = 5                # per category / language / model version
SCOPE_ORIGINS = {"live": {"real"}, "test": {"test"}, "imported": {"synthetic"},
                 "all": {"real", "test", "synthetic"}}


def _pct(num: int, den: int) -> Optional[float]:
    return round(100.0 * num / den, 1) if den else None


def _rate(successes: int, n: int, minimum: int = MIN_PER_GROUP) -> dict:
    return {"value_pct": _pct(successes, n), "n": n, "ci95_pct": wilson_interval(successes, n),
            "reliable": n >= minimum}


def _in_scope(complaint: Complaint, scope: str) -> bool:
    return complaint_origin(complaint.customer_id, complaint.data_origin) in SCOPE_ORIGINS[scope]


def _verified_rows(db: Session, scope: str, lo: Optional[datetime], hi: Optional[datetime]):
    q = (db.query(IncidentResolution, IssueAnalysis, Complaint)
         .join(Complaint, Complaint.id == IncidentResolution.complaint_id)
         .outerjoin(IssueAnalysis, IssueAnalysis.id == IncidentResolution.analysis_id))
    if lo:
        q = q.filter(IncidentResolution.resolved_at >= lo)
    if hi:
        q = q.filter(IncidentResolution.resolved_at <= hi)
    return [(r, a) for r, a, c in q.order_by(IncidentResolution.id).all() if _in_scope(c, scope)]


def _analyses(db: Session, scope: str, lo: Optional[datetime], hi: Optional[datetime]):
    q = db.query(IssueAnalysis, Complaint).join(Complaint, Complaint.id == IssueAnalysis.complaint_id)
    if lo:
        q = q.filter(IssueAnalysis.created_at >= lo)
    if hi:
        q = q.filter(IssueAnalysis.created_at <= hi)
    return [a for a, c in q.all() if _in_scope(c, scope)]


def _ml_category(a: Optional[IssueAnalysis]) -> Optional[str]:
    return ((a.ml_result or {}).get("category") if a else None)


def _llm_category(a: Optional[IssueAnalysis]) -> Optional[str]:
    return ((a.llm_result or {}).get("category") if a else None)


def compute_monitoring(db: Session, start: Optional[datetime] = None, end: Optional[datetime] = None,
                       scope: str = "live") -> dict:
    rows = _verified_rows(db, scope, start, end)
    analyses = _analyses(db, scope, start, end)
    n_verified = len(rows)
    assessed = [(r, a) for r, a in rows if r.predicted_category]          # a category was actually predicted
    undetermined = [(r, a) for r, a in rows if not r.predicted_category]
    correct = sum(r.predicted_category == r.verified_category for r, _ in assessed)

    # per-category precision / recall (predicted vs verified)
    report = classification_report([r.verified_category for r, _ in assessed],
                                   [r.predicted_category for r, _ in assessed]) if assessed else None
    per_category = {}
    if report:
        for label, m in report["per_class"].items():
            if m["support"] or m["precision"]:
                per_category[label] = {**m, "low_sample": m["support"] < MIN_PER_GROUP}

    # by prediction source (final prediction) and model-vs-fallback comparison on the same incidents
    by_source = {}
    for src in ("ml", "llm", "rules"):
        subset = [(r, a) for r, a in assessed if r.prediction_source == src]
        by_source[src] = _rate(sum(r.predicted_category == r.verified_category for r, _ in subset), len(subset))
    ml_rows = [(r, a) for r, a in rows if _ml_category(a)]
    llm_rows = [(r, a) for r, a in rows if _llm_category(a)]
    model_vs_fallback = {
        "ml_best_guess_on_all_verified": _rate(sum(_ml_category(a) == r.verified_category for r, a in ml_rows), len(ml_rows)),
        "llm_when_used": _rate(sum(_llm_category(a) == r.verified_category for r, a in llm_rows), len(llm_rows)),
        "note": "ML best guess is evaluated on every verified incident, including ones the LLM or rules finally answered.",
    }

    # corrections
    judged = [r for r, _ in rows if r.category_correct is not None]
    field_counts = Counter(f for r, _ in rows for f in (r.corrected_fields or []))
    corrections = {
        "any_correction": _rate(sum(1 for r in judged if (r.corrected_fields or [])), len(judged), MIN_VERIFIED_FOR_RATES),
        "by_field": dict(field_counts),
        "root_cause_correct": _rate(sum(1 for r in judged if r.root_cause_correct), len(judged), MIN_VERIFIED_FOR_RATES),
    }

    # language-wise
    by_lang: Dict[str, List] = defaultdict(list)
    for r, a in assessed:
        by_lang[(a.language_name if a and a.language_name else r.detected_language) or "unknown"].append(r)
    by_language = sorted(({"language": lang, **_rate(sum(r.predicted_category == r.verified_category for r in rs), len(rs))}
                          for lang, rs in by_lang.items()), key=lambda x: -x["n"])

    # pipeline health over ALL analyses in scope (not only verified ones)
    n_an = len(analyses)
    src_counts = Counter(a.prediction_source for a in analyses)
    pipeline = {
        "analyses_total": n_an,
        "by_source": dict(src_counts),
        "low_confidence_rate_pct": _pct(sum(1 for a in analyses if a.is_low_confidence), n_an),
        "llm_fallback_rate_pct": _pct(src_counts.get("llm", 0), n_an),
        "rules_fallback_rate_pct": _pct(src_counts.get("rules", 0), n_an),
        "undetermined_rate_pct": _pct(src_counts.get("undetermined", 0), n_an),
        "failed_analyses": sum(1 for a in analyses if a.status == "failed" or a.prediction_source == "none"),
        "llm_providers": dict(Counter((a.llm_result or {}).get("provider") for a in analyses
                                      if a.prediction_source == "llm")),
    }

    # new / unfamiliar issues
    known_subs = set(SUBCATEGORY_TO_CATEGORY)
    new_verified = Counter((r.verified_subcategory or r.verified_category) for r, _ in rows
                           if r.verified_category == NEW_ISSUE_CATEGORY
                           or (r.verified_subcategory and r.verified_subcategory not in known_subs))
    llm_proposed = Counter((a.llm_result or {}).get("subcategory") for a in analyses
                           if a.prediction_source == "llm" and (a.llm_result or {}).get("subcategory") not in known_subs)
    unfamiliar_flagged = sum(1 for a in analyses if a.fallback_reason and ("unfamiliar" in a.fallback_reason
                                                                          or "new kind of issue" in a.fallback_reason))
    unfamiliar = {
        "verified_new_issue_types": [{"label": k, "count": v} for k, v in new_verified.most_common(10)],
        "llm_proposed_unknown_subcategories": [{"label": k, "count": v} for k, v in llm_proposed.most_common(10) if k],
        "analyses_flagged_unfamiliar": unfamiliar_flagged,
        "undetermined_verified": len(undetermined),
    }

    # calibration of reported confidence against verified correctness
    calib = None
    if len(assessed) >= MIN_PER_GROUP:
        calib = calibration_report([float(a.confidence or 0) for r, a in assessed if a],
                                   [r.predicted_category == r.verified_category for r, a in assessed if a],
                                   threshold=settings.ML_CONFIDENCE_THRESHOLD)

    # by model version (spot regressions after a retrain)
    by_version: Dict[str, List] = defaultdict(list)
    for r, a in assessed:
        by_version[(a.model_version if a else None) or "unknown"].append(r)
    by_model_version = [{"model_version": v, **_rate(sum(r.predicted_category == r.verified_category for r in rs), len(rs))}
                        for v, rs in sorted(by_version.items())]

    sufficient = len(assessed) >= MIN_VERIFIED_FOR_RATES
    return {
        "window": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
                   "scope": scope, "generated_at": datetime.utcnow().isoformat()},
        "basis": {
            "verified_incidents": n_verified, "predictions_assessed": len(assessed),
            "minimum_for_reliable_rates": MIN_VERIFIED_FOR_RATES, "sample_sufficient": sufficient,
            "statement": ("Computed from admin-verified incidents on " + {
                "live": "real customer complaints only (synthetic imports and test accounts excluded).",
                "test": "test-account submissions only (NOT real-world performance).",
                "imported": "the synthetic imported dataset (NOT real-world performance).",
                "all": "ALL data including synthetic and test records (NOT real-world performance)."}[scope])
            + ("" if sufficient else f" Fewer than {MIN_VERIFIED_FOR_RATES} assessed predictions: "
               "treat every rate as indicative, not as measured accuracy."),
        },
        "accuracy": {
            "category": _rate(correct, len(assessed), MIN_VERIFIED_FOR_RATES),
            "incorrect_prediction_rate_pct": _pct(len(assessed) - correct, len(assessed)),
            "coverage_pct": _pct(len(assessed), n_verified),     # share of incidents where a category was predicted
        },
        "by_source": by_source,
        "model_vs_fallback": model_vs_fallback,
        "corrections": corrections,
        "per_category": per_category,
        "confusion_matrix": report["confusion_matrix"] if report else None,
        "by_language": by_language,
        "pipeline": pipeline,
        "unfamiliar": unfamiliar,
        "calibration": calib,
        "by_model_version": by_model_version,
    }


def render_markdown_report(m: dict) -> str:
    """Human-readable report generated from `compute_monitoring` output (no extra computation)."""
    w, b, acc = m["window"], m["basis"], m["accuracy"]["category"]
    fmt = lambda x: "N/A" if x is None else f"{x}%"
    ci = lambda r: f" (95% CI {r['ci95_pct'][0]}–{r['ci95_pct'][1]}%, n={r['n']}{'' if r['reliable'] else ', UNRELIABLE'})" \
        if r["ci95_pct"] else f" (n={r['n']})"
    lines = [f"# ZeroQ AI — Real-world model monitoring report",
             f"Generated {w['generated_at']} · scope **{w['scope']}** · window {w['start'] or 'start'} → {w['end'] or 'now'}", "",
             f"> {b['statement']}", "",
             f"- Admin-verified incidents: **{b['verified_incidents']}**; predictions assessed: **{b['predictions_assessed']}** "
             f"(minimum for reliable rates: {b['minimum_for_reliable_rates']})", "",
             "## Headline", f"- Category accuracy: **{fmt(acc['value_pct'])}**{ci(acc)}",
             f"- Incorrect-prediction rate: {fmt(m['accuracy']['incorrect_prediction_rate_pct'])}",
             f"- Prediction coverage (a category was proposed): {fmt(m['accuracy']['coverage_pct'])}"]
    c = m["corrections"]["any_correction"]
    lines += [f"- Admin correction rate: {fmt(c['value_pct'])}{ci(c)}; corrected fields: {m['corrections']['by_field'] or 'none'}", "",
              "## By prediction source"]
    for src, r in m["by_source"].items():
        lines.append(f"- {src}: {fmt(r['value_pct'])}{ci(r)}")
    mv = m["model_vs_fallback"]
    lines += [f"- ML best guess on all verified incidents: {fmt(mv['ml_best_guess_on_all_verified']['value_pct'])}"
              f"{ci(mv['ml_best_guess_on_all_verified'])}",
              f"- LLM when it was used: {fmt(mv['llm_when_used']['value_pct'])}{ci(mv['llm_when_used'])}", "",
              "## Per-category precision / recall (predicted vs verified)", "| Category | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for label, x in sorted(m["per_category"].items(), key=lambda kv: -kv[1]["support"]):
        flag = " ⚠ low sample" if x["low_sample"] else ""
        lines.append(f"| {label} | {x['precision']:.2f} | {x['recall']:.2f} | {x['f1']:.2f} | {x['support']}{flag} |")
    lines += ["", "## By language", "| Language | Accuracy | n |", "|---|---|---|"]
    for x in m["by_language"]:
        lines.append(f"| {x['language']} | {fmt(x['value_pct'])}{'' if x['reliable'] else ' ⚠'} | {x['n']} |")
    p = m["pipeline"]
    lines += ["", "## Pipeline health (all analyses in scope)",
              f"- Analyses: {p['analyses_total']} · by source: {p['by_source']}",
              f"- Low-confidence rate: {fmt(p['low_confidence_rate_pct'])} · LLM fallback: {fmt(p['llm_fallback_rate_pct'])} · "
              f"rule-based: {fmt(p['rules_fallback_rate_pct'])} · undetermined: {fmt(p['undetermined_rate_pct'])} · "
              f"failed: {p['failed_analyses']}",
              "", "## New / unfamiliar issues",
              f"- Verified new issue types: {m['unfamiliar']['verified_new_issue_types'] or 'none'}",
              f"- LLM-proposed subcategories outside the taxonomy: {m['unfamiliar']['llm_proposed_unknown_subcategories'] or 'none'}",
              f"- Analyses flagged unfamiliar: {m['unfamiliar']['analyses_flagged_unfamiliar']}", ""]
    if m["calibration"]:
        cal = m["calibration"]
        lines += ["## Confidence calibration (verified outcomes)", f"- ECE {cal['ece']} · Brier {cal['brier']}", ""]
    lines += ["## By model version"] + [f"- {x['model_version']}: {fmt(x['value_pct'])}{ci(x)}" for x in m["by_model_version"]]
    lines += ["", "_Models are promoted only through the retraining evaluation gate; this report never triggers promotion._"]
    return "\n".join(lines) + "\n"
