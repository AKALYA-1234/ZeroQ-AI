"""
Issue classifier: TF-IDF (word 1-2 grams + char 3-5 grams) + multinomial
logistic regression over subcategories. Category probabilities are the sum of
their subcategories' probabilities, which gives a steadier confidence signal
than the top subcategory alone.

Artifacts are versioned under models/trained/issue_classifier/ with an
`active.json` pointer, so a retrain can be evaluated before it is promoted.
"""
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.intelligence.evaluation import softmax
from app.intelligence.taxonomy import category_for

DEFAULT_MODEL_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "models", "trained", "issue_classifier"))
MODEL_DIR = os.environ.get("ISSUE_MODEL_DIR", DEFAULT_MODEL_DIR)
TOP_K = 3

_lock = threading.Lock()
_active_cache: Dict[str, "IssueClassifier"] = {}


class IssueClassifier:
    def __init__(self, pipeline: Pipeline, metadata: dict):
        self.pipeline = pipeline
        self.metadata = metadata

    @property
    def version(self) -> str:
        return self.metadata.get("version", "unknown")

    @classmethod
    def train(cls, texts: List[str], labels: List[str], weights: Optional[List[float]] = None,
              metadata: Optional[dict] = None) -> "IssueClassifier":
        features = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)),
        ])
        pipeline = Pipeline([
            ("features", features),
            ("clf", LogisticRegression(C=8.0, max_iter=2000, class_weight="balanced")),
        ])
        fit_params = {"clf__sample_weight": np.asarray(weights)} if weights is not None else {}
        pipeline.fit([t.lower() for t in texts], labels, **fit_params)
        version = f"issue-clf-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        meta = {"version": version, "trained_at": datetime.utcnow().isoformat(),
                "classes": list(pipeline.classes_), **(metadata or {})}
        return cls(pipeline, meta)

    @property
    def temperature(self) -> float:
        return float(self.metadata.get("temperature", 1.0))

    def decision_scores(self, texts: List[str]) -> np.ndarray:
        return self.pipeline.decision_function([(t or "").lower() for t in texts])

    def predict(self, text: str) -> dict:
        out = decide(list(self.pipeline.classes_), self.decision_scores([text])[0], self.temperature)
        out.update({"model_version": self.version, "temperature": self.temperature})
        return out

    # ── persistence ─────────────────────────────────────────────────────
    def save(self, model_dir: Optional[str] = None) -> str:
        model_dir = model_dir or MODEL_DIR
        os.makedirs(model_dir, exist_ok=True)
        path = os.path.join(model_dir, f"{self.version}.joblib")
        joblib.dump({"pipeline": self.pipeline, "metadata": self.metadata}, path)
        return path

    @classmethod
    def load(cls, path: str) -> "IssueClassifier":
        blob = joblib.load(path)
        return cls(blob["pipeline"], blob["metadata"])


def _pointer_path(model_dir: str) -> str:
    return os.path.join(model_dir, "active.json")


def promote(classifier: IssueClassifier, model_dir: Optional[str] = None) -> None:
    model_dir = model_dir or MODEL_DIR
    path = classifier.save(model_dir)
    with _lock:
        with open(_pointer_path(model_dir), "w", encoding="utf-8") as fh:
            json.dump({"version": classifier.version, "path": os.path.basename(path)}, fh)
        _active_cache[model_dir] = classifier


def load_active(model_dir: Optional[str] = None) -> Optional[IssueClassifier]:
    model_dir = model_dir or MODEL_DIR
    with _lock:
        if model_dir in _active_cache:
            return _active_cache[model_dir]
        pointer = _pointer_path(model_dir)
        if not os.path.exists(pointer):
            return None
        with open(pointer, encoding="utf-8") as fh:
            info = json.load(fh)
        path = os.path.join(model_dir, info["path"])
        if not os.path.exists(path):
            return None
        clf = IssueClassifier.load(path)
        _active_cache[model_dir] = clf
        return clf


def save_evaluation(version: str, metrics: dict, model_dir: Optional[str] = None) -> str:
    """Persist the full evaluation record next to the artifact (kept for rejected candidates too)."""
    model_dir = model_dir or MODEL_DIR
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, f"{version}.eval.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=1, default=str)
    return path


def clear_cache() -> None:
    with _lock:
        _active_cache.clear()


def _category_mass(classes: List[str], probs: np.ndarray) -> Dict[str, float]:
    mass: Dict[str, float] = {}
    for cls_name, p in zip(classes, probs):
        cat = category_for(cls_name, default=cls_name)
        mass[cat] = mass.get(cat, 0.0) + float(p)
    return mass


def decide(classes: List[str], scores: np.ndarray, temperature: float = 1.0) -> dict:
    """Category / subcategory decision plus calibrated confidence.

    The *decision* uses the unscaled model probabilities (T=1): temperature scaling must
    calibrate confidence without changing what is predicted, and because category
    probability is a sum over subcategories, sharpening could otherwise flip the category.
    The reported confidences use the temperature-scaled probabilities."""
    raw = softmax(scores)
    cal = softmax(scores / temperature)
    raw_mass, cal_mass = _category_mass(classes, raw), _category_mass(classes, cal)
    best_cat = max(raw_mass, key=raw_mass.get)
    order = np.argsort(raw)[::-1]
    in_cat = [i for i in order if category_for(classes[i], default=classes[i]) == best_cat]
    best_sub = classes[in_cat[0]]       # best subcategory *within* the chosen category
    cal_order = np.argsort(cal)[::-1]
    return {
        "category": best_cat,
        "category_confidence": round(cal_mass[best_cat], 4),
        "subcategory": best_sub if best_sub != best_cat else None,
        "subcategory_confidence": round(float(cal[in_cat[0]]), 4),
        "top_subcategories": [{"label": classes[i], "probability": round(float(cal[i]), 4)} for i in cal_order[:TOP_K]],
        "category_probabilities": {k: round(v, 4) for k, v in sorted(cal_mass.items(), key=lambda kv: -kv[1])[:5]},
    }
