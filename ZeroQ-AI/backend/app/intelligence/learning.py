"""
Controlled model-improvement pipeline.

Training data = historical complaints whose root cause was verified by the
quality team + curated seed phrases + admin-verified platform incidents.
Unverified AI predictions are never used. A candidate model is promoted only
if it does not regress on (a) the independent multilingual benchmark and
(b) a held-out slice of verified incidents (when there are enough).
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence import classifier as clf_registry
from app.intelligence.benchmark import BENCHMARK
from app.intelligence.classifier import IssueClassifier
from app.intelligence.seeds import SEED_PHRASES
from app.intelligence.taxonomy import OPERATIONAL_CATEGORY, NEW_ISSUE_CATEGORY, SUBCATEGORY_TO_CATEGORY
from app.intelligence.understanding import understand
from app.models.intelligence import IncidentResolution, ModelTrainingRun

logger = logging.getLogger(__name__)

VERIFIED_WEIGHT = 2.0
HOLDOUT_EVERY = 5            # every 5th verified incident (by id) is held out for evaluation
MIN_HOLDOUT = 5
REGRESSION_TOLERANCE = 0.02


class NotEnoughVerifiedData(Exception):
    pass


def _historical_rows(db: Session) -> List[Tuple[str, str]]:
    rows = db.execute(sql_text(
        "SELECT DISTINCT c.description, c.complaint_subcategory FROM complaints c "
        "JOIN investigations i ON i.complaint_id = c.id "
        "WHERE i.is_root_cause_verified = 1 AND c.complaint_subcategory IS NOT NULL "
        "AND c.description IS NOT NULL"
    )).fetchall()
    return [(r[0], r[1]) for r in rows]


def _verified_label(r: IncidentResolution) -> str:
    if r.verified_subcategory:
        return r.verified_subcategory
    return r.verified_category


def build_training_set(db: Session, exclude_ids: Optional[set] = None):
    texts, labels, weights, sources = [], [], [], {"historical_verified": 0, "seed": 0, "admin_verified": 0}
    for text, label in _historical_rows(db):
        texts.append(text); labels.append(label); weights.append(1.0)
        sources["historical_verified"] += 1
    for label, phrases in SEED_PHRASES.items():
        for p in phrases:
            texts.append(p); labels.append(label); weights.append(1.0)
            sources["seed"] += 1
    verified = db.query(IncidentResolution).all()
    for r in verified:
        if exclude_ids and r.id in exclude_ids:
            continue
        text = r.english_text or r.original_text
        if not text:
            continue
        texts.append(text); labels.append(_verified_label(r)); weights.append(VERIFIED_WEIGHT)
        sources["admin_verified"] += 1
    return texts, labels, weights, sources


def evaluate_benchmark(model: IssueClassifier) -> dict:
    results, correct, confident, confident_correct = [], 0, 0, 0
    for text, _lang, expected in BENCHMARK:
        u = understand(text, allow_llm=False)
        pred = model.predict(u["english_text"])
        ok = pred["category"] == expected
        is_conf = pred["category_confidence"] >= settings.ML_CONFIDENCE_THRESHOLD
        correct += ok
        confident += is_conf
        confident_correct += ok and is_conf
        results.append({"text": text, "expected": expected, "predicted": pred["category"],
                        "confidence": pred["category_confidence"], "correct": ok})
    n = len(BENCHMARK)
    return {
        "n": n,
        "accuracy": round(correct / n, 4),
        "confident_share": round(confident / n, 4),
        "confident_accuracy": round(confident_correct / confident, 4) if confident else None,
        "items": results,
    }


def evaluate_holdout(model: IssueClassifier, holdout: List[IncidentResolution]) -> Optional[dict]:
    if len(holdout) < MIN_HOLDOUT:
        return None
    correct = 0
    for r in holdout:
        pred = model.predict(r.english_text or r.original_text or "")
        correct += pred["category"] == r.verified_category
    return {"n": len(holdout), "accuracy": round(correct / len(holdout), 4)}


def _summary(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k != "benchmark_items"}


def retrain(db: Session, trigger: str = "manual", force: bool = False, user: Optional[str] = None,
            model_dir: Optional[str] = None) -> ModelTrainingRun:
    unused = db.query(IncidentResolution).filter(IncidentResolution.used_in_training_run.is_(None)).all()
    if trigger != "bootstrap" and not force and len(unused) < settings.RETRAIN_MIN_NEW_SAMPLES:
        raise NotEnoughVerifiedData(
            f"{len(unused)} new verified incidents; {settings.RETRAIN_MIN_NEW_SAMPLES} required (or force).")

    verified = db.query(IncidentResolution).order_by(IncidentResolution.id).all()
    holdout = [r for r in verified if r.id % HOLDOUT_EVERY == 0]
    texts, labels, weights, sources = build_training_set(db, exclude_ids={r.id for r in holdout})
    candidate = IssueClassifier.train(texts, labels, weights, metadata={"training_sources": sources})

    bench = evaluate_benchmark(candidate)
    hold = evaluate_holdout(candidate, holdout)
    metrics = {"benchmark_accuracy": bench["accuracy"], "benchmark_confident_share": bench["confident_share"],
               "benchmark_confident_accuracy": bench["confident_accuracy"], "benchmark_n": bench["n"],
               "verified_holdout": hold, "training_sources": sources, "benchmark_items": bench["items"]}

    current = clf_registry.load_active(model_dir)
    prev = None
    promoted, notes = True, "bootstrap" if current is None else ""
    if current is not None:
        cur_bench = evaluate_benchmark(current)
        cur_hold = evaluate_holdout(current, holdout)
        prev = {"model_version": current.version, "benchmark_accuracy": cur_bench["accuracy"],
                "verified_holdout": cur_hold}
        if bench["accuracy"] < cur_bench["accuracy"] - REGRESSION_TOLERANCE:
            promoted, notes = False, "rejected: benchmark accuracy regressed"
        elif hold and cur_hold and hold["accuracy"] < cur_hold["accuracy"] - REGRESSION_TOLERANCE:
            promoted, notes = False, "rejected: verified-holdout accuracy regressed"
        else:
            notes = "promoted: no regression"

    candidate.metadata["metrics"] = _summary(metrics)
    if promoted:
        clf_registry.promote(candidate, model_dir)

    run = ModelTrainingRun(
        model_version=candidate.version, trigger=trigger,
        status="completed" if promoted else "rejected", promoted=promoted,
        n_training_samples=len(texts), n_verified_samples=sources["admin_verified"],
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
    logger.info("Training run %s: %s (benchmark=%.3f)", run.id, run.status, bench["accuracy"])
    return run


def get_classifier(db: Session, model_dir: Optional[str] = None) -> IssueClassifier:
    model = clf_registry.load_active(model_dir)
    if model is None:
        retrain(db, trigger="bootstrap", model_dir=model_dir)
        model = clf_registry.load_active(model_dir)
    return model


def learning_status(db: Session, model_dir: Optional[str] = None) -> dict:
    model = clf_registry.load_active(model_dir)
    verified = db.query(IncidentResolution).all()
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
