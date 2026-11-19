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

    def predict(self, text: str) -> dict:
        probs = self.pipeline.predict_proba([(text or "").lower()])[0]
        classes = list(self.pipeline.classes_)
        order = np.argsort(probs)[::-1]
        cat_probs: Dict[str, float] = {}
        for cls_name, p in zip(classes, probs):
            cat = category_for(cls_name, default=cls_name)
            cat_probs[cat] = cat_probs.get(cat, 0.0) + float(p)
        best_cat = max(cat_probs, key=cat_probs.get)
        # Best subcategory *within* the best category keeps the pair consistent.
        in_cat = [i for i in order if category_for(classes[i], default=classes[i]) == best_cat]
        best_sub = classes[in_cat[0]]
        return {
            "category": best_cat,
            "category_confidence": round(cat_probs[best_cat], 4),
            "subcategory": best_sub if best_sub != best_cat else None,
            "subcategory_confidence": round(float(probs[in_cat[0]]), 4),
            "top_subcategories": [
                {"label": classes[i], "probability": round(float(probs[i]), 4)} for i in order[:TOP_K]
            ],
            "category_probabilities": {
                k: round(v, 4) for k, v in sorted(cat_probs.items(), key=lambda kv: -kv[1])[:5]
            },
            "model_version": self.version,
        }

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


def clear_cache() -> None:
    with _lock:
        _active_cache.clear()
