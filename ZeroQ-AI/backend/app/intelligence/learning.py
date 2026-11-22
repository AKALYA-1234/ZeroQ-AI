"""
Controlled model-improvement pipeline.

Training data = historical complaints whose root cause was verified by the
quality team + curated seed phrases + admin-verified platform incidents.
Unverified AI predictions are never used. A candidate model is promoted only
if it does not regress on (a) the independent multilingual benchmark and
(b) a held-out slice of verified incidents (when there are enough).
"""
import logging
from collections import defaultdict

import numpy as np
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_, text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence import classifier as clf_registry
from app.intelligence.eval_dataset import EVAL_ITEMS, UNSUPPORTED_OFFLINE
from app.intelligence.evaluation import (
    calibration_report, classification_report, dataset_fingerprint, fit_temperature, grouped_template_folds,
    normalize_template,
)
from app.intelligence.classifier import IssueClassifier
from app.intelligence.seeds import SEED_PHRASES
from app.intelligence.taxonomy import (
    OPERATIONAL_CATEGORY, NEW_ISSUE_CATEGORY, SUBCATEGORY_TO_CATEGORY, category_for,
)
from app.intelligence.understanding import understand
from app.models.complaint import Complaint
from app.models.intelligence import IncidentResolution, ModelTrainingRun

logger = logging.getLogger(__name__)

VERIFIED_WEIGHT = 2.0
HOLDOUT_EVERY = 5            # every 5th verified incident (by id) is held out for evaluation
MIN_HOLDOUT = 5
HISTORICAL_FOLDS = 5
# A candidate is promoted only if every applicable check passes.
PROMOTION_CRITERIA = {
    "min_independent_accuracy": 0.75,   # absolute floor on the independent multilingual set
    "min_independent_macro_f1": 0.70,
    "max_regression": 0.02,             # vs the active model (independent set + verified holdout)
}


class NotEnoughVerifiedData(Exception):
    pass


def _historical_rows(db: Session) -> List[Tuple[str, str]]:
    rows = db.execute(sql_text(
        "SELECT DISTINCT c.description, c.complaint_subcategory FROM complaints c "
        "JOIN investigations i ON i.complaint_id = c.id "
        "WHERE i.is_root_cause_verified = :verified AND c.complaint_subcategory IS NOT NULL "
        "AND c.description IS NOT NULL"
    ), {"verified": True}).fetchall()   # bound boolean: portable across SQLite and PostgreSQL
    return [(r[0], r[1]) for r in rows]


def _verified_label(r: IncidentResolution) -> str:
    if r.verified_subcategory:
        return r.verified_subcategory
    return r.verified_category


def trainable_resolutions(db: Session) -> List[IncidentResolution]:
    """Admin-verified incidents eligible for training / real-world evaluation: everything except
    test-account submissions (origin.py). Ordered by id."""
    return (db.query(IncidentResolution)
            .join(Complaint, Complaint.id == IncidentResolution.complaint_id)
            .filter(or_(Complaint.data_origin.is_(None), Complaint.data_origin != "test"))
            .order_by(IncidentResolution.id).all())


def training_rows(db: Session, exclude_ids: Optional[set] = None) -> List[Tuple[str, str, str, float]]:
    """(text, label, source, weight) for every training example. Only verified sources:
    quality-team-verified historical investigations, curated seeds, admin-verified incidents."""
    rows = [(t, l, "historical_verified", 1.0) for t, l in _historical_rows(db)]
    rows += [(p, label, "seed", 1.0) for label, phrases in SEED_PHRASES.items() for p in phrases]
    for r in trainable_resolutions(db):
        if exclude_ids and r.id in exclude_ids:
            continue
        text = r.english_text or r.original_text
        if text:
            rows.append((text, _verified_label(r), "admin_verified", VERIFIED_WEIGHT))
    return rows


def build_training_set(db: Session, exclude_ids: Optional[set] = None):
    rows = training_rows(db, exclude_ids)
    sources = {"historical_verified": 0, "seed": 0, "admin_verified": 0}
    for _, _, src, _ in rows:
        sources[src] += 1
    return [r[0] for r in rows], [r[1] for r in rows], [r[3] for r in rows], sources


# ── evaluations ────────────────────────────────────────────────────────────

def _score_items(model: IssueClassifier, items) -> dict:
    y_true, y_pred, confs, details = [], [], [], []
    by_lang = defaultdict(lambda: [0, 0])
    for text, lang, expected, group in items:
        u = understand(text, allow_llm=False)
        pred = model.predict(u["english_text"])
        ok = pred["category"] == expected
        y_true.append(expected); y_pred.append(pred["category"]); confs.append(pred["category_confidence"])
        by_lang[lang][0] += 1
        by_lang[lang][1] += ok
        details.append({"text": text, "language": lang, "issue_group": group, "expected": expected,
                        "predicted": pred["category"], "confidence": pred["category_confidence"],
                        "translation_method": u["translation_method"], "correct": ok})
    report = classification_report(y_true, y_pred, labels=sorted(set(y_true) | set(y_pred)))
    report["calibration"] = calibration_report(confs, [d["correct"] for d in details],
                                               threshold=settings.ML_CONFIDENCE_THRESHOLD)
    report["by_language"] = {l: {"n": n, "accuracy": round(c / n, 4)} for l, (n, c) in sorted(by_lang.items())}
    report["items"] = details
    return report


def evaluate_independent(model: IssueClassifier) -> dict:
    return _score_items(model, EVAL_ITEMS)


def evaluate_unsupported(model: IssueClassifier) -> dict:
    return _score_items(model, UNSUPPORTED_OFFLINE)


def evaluate_benchmark(model: IssueClassifier) -> dict:
    """Backward-compatible summary of the independent evaluation."""
    r = evaluate_independent(model)
    sel = r["calibration"]["selective"]
    return {"n": r["n"], "accuracy": r["accuracy"], "confident_share": sel["coverage"],
            "confident_accuracy": sel["accuracy"], "items": r["items"]}


def evaluate_historical_grouped(db: Session, n_folds: int = HISTORICAL_FOLDS) -> Optional[dict]:
    """Leakage-safe CV on imported complaint text: whole templates are held out per fold.
    Fold models train on the other templates + seeds; admin-verified rows are excluded so the
    number describes generalisation from the historical dataset only."""
    hist = _historical_rows(db)
    if len({normalize_template(t) for t, _ in hist}) < n_folds:
        return None
    seeds = [(p, label) for label, phrases in SEED_PHRASES.items() for p in phrases]
    y_true, y_pred, confs, sub_hits = [], [], [], 0
    oof_scores, oof_labels = [], []
    for train_idx, test_idx in grouped_template_folds(hist, n_folds):
        train = [hist[i] for i in train_idx] + seeds
        fold_model = IssueClassifier.train([t for t, _ in train], [l for _, l in train])
        classes = list(fold_model.pipeline.classes_)
        scores = fold_model.decision_scores([hist[i][0] for i in test_idx])
        for row, i in zip(scores, test_idx):
            text, sub = hist[i]
            pred = fold_model.predict(text)
            y_true.append(category_for(sub)); y_pred.append(pred["category"])
            confs.append(pred["category_confidence"])
            sub_hits += pred["subcategory"] == sub
            if sub in classes:   # out-of-fold scores for temperature fitting
                oof_scores.append(row); oof_labels.append(classes.index(sub))
    report = classification_report(y_true, y_pred)
    report["subcategory_accuracy"] = round(sub_hits / len(y_true), 4)
    report["calibration"] = calibration_report(confs, [t == p for t, p in zip(y_true, y_pred)],
                                               threshold=settings.ML_CONFIDENCE_THRESHOLD)
    report["n_templates"] = len({normalize_template(t) for t, _ in hist})
    report["folds"] = n_folds
    report["fitted_temperature"] = fit_temperature(np.array(oof_scores), np.array(oof_labels))
    return report


def evaluate_holdout(model: IssueClassifier, holdout: List[IncidentResolution]) -> Optional[dict]:
    if len(holdout) < MIN_HOLDOUT:
        return None
    y_true = [r.verified_category for r in holdout]
    y_pred = [model.predict(r.english_text or r.original_text or "")["category"] for r in holdout]
    return classification_report(y_true, y_pred)


def _strip_items(report: Optional[dict]) -> Optional[dict]:
    if report is None:
        return None
    return {k: v for k, v in report.items() if k != "items"}


def check_promotion(candidate: dict, current: Optional[dict]) -> Tuple[bool, List[dict]]:
    """Apply PROMOTION_CRITERIA. Returns (passed, [check results])."""
    ind = candidate["independent_multilingual"]
    checks = [
        {"check": "independent accuracy >= floor", "value": ind["accuracy"],
         "required": PROMOTION_CRITERIA["min_independent_accuracy"]},
        {"check": "independent macro-F1 >= floor", "value": ind["macro_f1"],
         "required": PROMOTION_CRITERIA["min_independent_macro_f1"]},
    ]
    if current:
        tol = PROMOTION_CRITERIA["max_regression"]
        cur_ind = current["independent_multilingual"]
        checks.append({"check": "no independent accuracy regression", "value": ind["accuracy"],
                       "required": round(cur_ind["accuracy"] - tol, 4)})
        checks.append({"check": "no independent macro-F1 regression", "value": ind["macro_f1"],
                       "required": round(cur_ind["macro_f1"] - tol, 4)})
        hold, cur_hold = candidate.get("verified_holdout"), current.get("verified_holdout")
        if hold and cur_hold:
            checks.append({"check": "no verified-holdout accuracy regression", "value": hold["accuracy"],
                           "required": round(cur_hold["accuracy"] - tol, 4)})
    for c in checks:
        c["passed"] = c["value"] >= c["required"]
    return all(c["passed"] for c in checks), checks


def _evaluate_all(db: Session, model: IssueClassifier, holdout, historical: Optional[dict]) -> dict:
    return {
        "independent_multilingual": evaluate_independent(model),
        "unsupported_offline": evaluate_unsupported(model),
        "historical_grouped": historical,
        "verified_holdout": evaluate_holdout(model, holdout),
    }


def retrain(db: Session, trigger: str = "manual", force: bool = False, user: Optional[str] = None,
            model_dir: Optional[str] = None) -> ModelTrainingRun:
    unused = [r for r in trainable_resolutions(db) if r.used_in_training_run is None]
    if trigger != "bootstrap" and not force and len(unused) < settings.RETRAIN_MIN_NEW_SAMPLES:
        raise NotEnoughVerifiedData(
            f"{len(unused)} new verified incidents; {settings.RETRAIN_MIN_NEW_SAMPLES} required (or force).")

    verified = trainable_resolutions(db)
    holdout = [r for r in verified if r.id % HOLDOUT_EVERY == 0]
    rows = training_rows(db, exclude_ids={r.id for r in holdout})
    sources = {"historical_verified": 0, "seed": 0, "admin_verified": 0}
    for _, _, src, _ in rows:
        sources[src] += 1
    fingerprint = dataset_fingerprint([(t, l, src) for t, l, src, _ in rows])
    candidate = IssueClassifier.train([r[0] for r in rows], [r[1] for r in rows], [r[3] for r in rows],
                                      metadata={"training_sources": sources, "dataset_fingerprint": fingerprint})

    historical = evaluate_historical_grouped(db)   # property of the data + method, shared by both models
    # Uncalibrated independent result is kept for comparison; the temperature is fitted only on
    # out-of-fold historical predictions, never on the independent set.
    uncalibrated = evaluate_independent(candidate)["calibration"]
    candidate.metadata["temperature"] = historical["fitted_temperature"] if historical else 1.0
    cand_eval = _evaluate_all(db, candidate, holdout, historical)
    current = clf_registry.load_active(model_dir)
    cur_eval = _evaluate_all(db, current, holdout, historical) if current is not None else None
    passed, checks = check_promotion(cand_eval, cur_eval)
    promoted = passed
    notes = ("promoted" if promoted else "rejected") + ": " + "; ".join(
        f"{c['check']} ({c['value']} vs {c['required']})" for c in checks if not c["passed"]) if not passed \
        else ("bootstrap: all criteria passed" if current is None else "promoted: all criteria passed")

    ind = cand_eval["independent_multilingual"]
    metrics = {
        # summary keys (UI / status)
        "benchmark_accuracy": ind["accuracy"],
        "benchmark_macro_f1": ind["macro_f1"],
        "benchmark_confident_share": ind["calibration"]["selective"]["coverage"],
        "benchmark_confident_accuracy": ind["calibration"]["selective"]["accuracy"],
        "benchmark_n": ind["n"],
        "historical_grouped_accuracy": historical["accuracy"] if historical else None,
        "verified_holdout": {"n": cand_eval["verified_holdout"]["n"],
                             "accuracy": cand_eval["verified_holdout"]["accuracy"]}
        if cand_eval["verified_holdout"] else None,
        "training_sources": sources,
        "dataset_fingerprint": fingerprint,
        "temperature": candidate.temperature,
        "calibration_before_temperature": {k: uncalibrated[k] for k in ("ece", "brier", "selective")},
        "calibration_after_temperature": {k: ind["calibration"][k] for k in ("ece", "brier", "selective")},
        "promotion_checks": checks,
        # full evaluations
        "evaluations": {k: _strip_items(v) for k, v in cand_eval.items()},
        "benchmark_items": ind["items"],
    }
    prev = None
    if cur_eval is not None:
        cur_ind = cur_eval["independent_multilingual"]
        prev = {"model_version": current.version, "benchmark_accuracy": cur_ind["accuracy"],
                "benchmark_macro_f1": cur_ind["macro_f1"],
                "verified_holdout": _strip_items(cur_eval["verified_holdout"])}

    candidate.metadata["metrics"] = {k: v for k, v in metrics.items() if k not in ("benchmark_items", "evaluations")}
    if promoted:
        clf_registry.promote(candidate, model_dir)
    clf_registry.save_evaluation(candidate.version, metrics, model_dir)

    run = ModelTrainingRun(
        model_version=candidate.version, trigger=trigger,
        status="completed" if promoted else "rejected", promoted=promoted,
        n_training_samples=len(rows), n_verified_samples=sources["admin_verified"],
        metrics=metrics, previous_metrics=prev, notes=notes, created_by=user,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()
    if promoted:
        for r in unused:
            r.used_in_training_run = run.id
    db.commit()
    db.refresh(run)
    logger.info("Training run %s: %s (independent accuracy=%.3f, macro-F1=%.3f)",
                run.id, run.status, ind["accuracy"], ind["macro_f1"])
    return run


def get_classifier(db: Session, model_dir: Optional[str] = None) -> IssueClassifier:
    model = clf_registry.load_active(model_dir)
    if model is None:
        retrain(db, trigger="bootstrap", model_dir=model_dir)
        model = clf_registry.load_active(model_dir)
    return model


def learning_status(db: Session, model_dir: Optional[str] = None) -> dict:
    model = clf_registry.load_active(model_dir)
    verified = trainable_resolutions(db)
    unused = [r for r in verified if r.used_in_training_run is None]
    judged = [r for r in verified if r.category_correct is not None]
    incorrect = [r for r in judged if not r.category_correct]
    known = set(model.metadata.get("classes", [])) if model else set()
    new_issue_counts = {}
    for r in verified:
        label = _verified_label(r)
        if r.verified_category in (OPERATIONAL_CATEGORY, NEW_ISSUE_CATEGORY) or label not in known:
            new_issue_counts[label] = new_issue_counts.get(label, 0) + 1
    runs = db.query(ModelTrainingRun).order_by(ModelTrainingRun.created_at.desc()).limit(10).all()
    return {
        "active_model": {
            "version": model.version if model else None,
            "trained_at": model.metadata.get("trained_at") if model else None,
            "metrics": model.metadata.get("metrics") if model else None,
            "n_classes": len(known),
        },
        "verified_incidents": len(verified),
        "pending_training_samples": len(unused),
        "retrain_threshold": settings.RETRAIN_MIN_NEW_SAMPLES,
        "retrain_ready": len(unused) >= settings.RETRAIN_MIN_NEW_SAMPLES,
        "incorrect_predictions": len(incorrect),
        "admin_correction_rate": round(len(incorrect) / len(judged), 4) if judged else None,
        "frequent_new_issues": sorted(
            ({"label": k, "count": v, "known_to_model": k in known} for k, v in new_issue_counts.items()),
            key=lambda x: -x["count"])[:8],
        "known_subcategories": sorted(SUBCATEGORY_TO_CATEGORY.keys()),
        "training_runs": [{
            "id": r.id, "model_version": r.model_version, "trigger": r.trigger, "status": r.status,
            "promoted": r.promoted, "n_training_samples": r.n_training_samples,
            "n_verified_samples": r.n_verified_samples,
            "benchmark_accuracy": (r.metrics or {}).get("benchmark_accuracy"),
            "verified_holdout": (r.metrics or {}).get("verified_holdout"),
            "notes": r.notes, "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in runs],
    }
