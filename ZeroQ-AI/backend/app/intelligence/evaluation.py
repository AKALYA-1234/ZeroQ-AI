"""
Model evaluation pipeline for the issue classifier.

Four separately reported evaluations (never blended into one number):
  1. independent_multilingual — eval_dataset.EVAL_ITEMS through the full offline
     understanding path (language detection → gloss → classifier). Category level.
  2. historical_grouped — leakage-safe cross-validation on the imported complaint
     text: folds are grouped by *normalised template*, so a sentence used for
     training never appears in its test fold. Measures generalisation to unseen
     wording. Seed phrases are always training-only.
  3. verified_holdout — every 5th admin-verified incident (by id), held out.
  4. unsupported_offline — languages outside the offline glossary (needs LLM).

Metrics: accuracy, macro precision/recall/F1, per-class P/R/F1/support/FPR/FNR,
confusion matrix, calibration (ECE, Brier, reliability bins) and selective
accuracy/coverage at the production confidence threshold.
"""
import hashlib
import json
import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

CALIBRATION_BINS = 10
TEMPERATURE_GRID = np.logspace(-2, 0.7, 120)   # 0.01 … ~5


def normalize_template(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def dataset_fingerprint(rows: Sequence[Tuple[str, str, str]]) -> str:
    """sha256 over the sorted (text, label, source) triples — identifies the exact training set."""
    payload = json.dumps(sorted([list(r) for r in rows]), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def classification_report(y_true: List[str], y_pred: List[str], labels: Optional[List[str]] = None) -> dict:
    labels = labels or sorted(set(y_true) | set(y_pred))
    idx = {l: i for i, l in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            matrix[idx[t]][idx[p]] += 1
    n = len(y_true)
    per_class, f1s, precs, recs = {}, [], [], []
    for l in labels:
        i = idx[l]
        tp = matrix[i][i]
        fp = sum(matrix[r][i] for r in range(len(labels))) - tp
        fn = sum(matrix[i]) - tp
        tn = n - tp - fp - fn
        precision, recall = _safe_div(tp, tp + fp), _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        support = tp + fn
        per_class[l] = {
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "support": support,
            "false_positive_rate": round(_safe_div(fp, fp + tn), 4),
            "false_negative_rate": round(_safe_div(fn, fn + tp), 4),
        }
        if support:  # macro averages over classes present in the ground truth
            f1s.append(f1); precs.append(precision); recs.append(recall)
    correct = sum(t == p for t, p in zip(y_true, y_pred))
    return {
        "n": n,
        "accuracy": round(_safe_div(correct, n), 4),
        "macro_precision": round(_safe_div(sum(precs), len(precs)), 4),
        "macro_recall": round(_safe_div(sum(recs), len(recs)), 4),
        "macro_f1": round(_safe_div(sum(f1s), len(f1s)), 4),
        "per_class": per_class,
        "confusion_matrix": {"labels": labels, "matrix": matrix},
    }


def calibration_report(confidences: List[float], correct: List[bool], threshold: Optional[float] = None,
                       n_bins: int = CALIBRATION_BINS) -> dict:
    n = len(confidences)
    bins = defaultdict(list)
    for c, ok in zip(confidences, correct):
        bins[min(n_bins - 1, int(c * n_bins))].append((c, ok))
    ece, reliability = 0.0, []
    for b in range(n_bins):
        items = bins.get(b, [])
        if not items:
            continue
        conf = sum(c for c, _ in items) / len(items)
        acc = sum(ok for _, ok in items) / len(items)
        ece += len(items) / n * abs(conf - acc)
        reliability.append({"bin": f"{b / n_bins:.1f}-{(b + 1) / n_bins:.1f}", "n": len(items),
                            "mean_confidence": round(conf, 4), "accuracy": round(acc, 4)})
    brier = _safe_div(sum((c - (1.0 if ok else 0.0)) ** 2 for c, ok in zip(confidences, correct)), n)
    report = {"ece": round(ece, 4), "brier": round(brier, 4), "reliability": reliability}
    if threshold is not None:
        kept = [ok for c, ok in zip(confidences, correct) if c >= threshold]
        report["selective"] = {"threshold": threshold, "coverage": round(_safe_div(len(kept), n), 4),
                               "accuracy": round(_safe_div(sum(kept), len(kept)), 4) if kept else None}
    return report


def grouped_template_folds(rows: Sequence[Tuple[str, str]], n_folds: int = 5) -> List[Tuple[List[int], List[int]]]:
    """K folds over row indices where all rows sharing a normalised template stay in one fold.
    Templates are dealt round-robin per label so each fold sees a spread of classes."""
    by_template: Dict[str, List[int]] = defaultdict(list)
    template_label: Dict[str, str] = {}
    for i, (text, label) in enumerate(rows):
        key = normalize_template(text)
        by_template[key].append(i)
        template_label.setdefault(key, label)
    by_label: Dict[str, List[str]] = defaultdict(list)
    for key in sorted(by_template):
        by_label[template_label[key]].append(key)
    fold_of: Dict[str, int] = {}
    counter = 0
    for label in sorted(by_label):
        for key in by_label[label]:
            fold_of[key] = counter % n_folds
            counter += 1
    folds = []
    for f in range(n_folds):
        test = sorted(i for key, idxs in by_template.items() if fold_of[key] == f for i in idxs)
        train = sorted(i for key, idxs in by_template.items() if fold_of[key] != f for i in idxs)
        if test:
            folds.append((train, test))
    return folds


def softmax(scores: np.ndarray) -> np.ndarray:
    z = scores - scores.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def fit_temperature(scores: np.ndarray, labels: np.ndarray) -> float:
    """Temperature scaling: the T minimising negative log-likelihood of the true class over
    out-of-fold decision scores. T < 1 sharpens an under-confident model, T > 1 softens."""
    if len(scores) == 0:
        return 1.0
    best_t, best_nll = 1.0, float("inf")
    rows = np.arange(len(labels))
    for t in TEMPERATURE_GRID:
        probs = softmax(scores / t)
        nll = -np.log(np.clip(probs[rows, labels], 1e-12, None)).mean()
        if nll < best_nll:
            best_t, best_nll = float(t), nll
    return round(best_t, 4)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    """95% Wilson score interval for a proportion (returns [low, high] in %, or None if n == 0).
    Far better behaved than the normal approximation at small n or extreme rates."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return [round(100 * max(0.0, centre - half), 1), round(100 * min(1.0, centre + half), 1)]
