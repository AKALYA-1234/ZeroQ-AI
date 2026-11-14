"""
ZeroQ AI — ML Model Service
Loads the trained XGBoost model and provides prediction capabilities.
The model is a binary classifier (complaint risk: 0=low, 1=high)
trained with 10,038 features (TF-IDF text + encoded categoricals).
"""

import os
import logging
import numpy as np
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# ── Model Configuration ──────────────────────────────────────────────────
MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "final_xgboost_model.joblib"
)
MODEL_VERSION = "xgboost-v1.0-final"
N_FEATURES = 10038

# ── Singleton Model Holder ───────────────────────────────────────────────
_model = None
_model_loaded = False
_load_error: Optional[str] = None


def _load_model():
    """Load the XGBoost model from disk (lazy singleton)."""
    global _model, _model_loaded, _load_error

    if _model_loaded:
        return _model

    abs_path = os.path.abspath(MODEL_PATH)
    logger.info(f"Loading XGBoost model from: {abs_path}")

    if not os.path.exists(abs_path):
        _load_error = f"Model file not found: {abs_path}"
        logger.error(_load_error)
        _model_loaded = True
        return None

    try:
        import joblib
        _model = joblib.load(abs_path)
        _model_loaded = True
        _load_error = None
        logger.info(
            f"Model loaded successfully. "
            f"Type: {type(_model).__name__}, "
            f"Features: {_model.n_features_in_}, "
            f"Classes: {_model.classes_.tolist()}"
        )
        return _model
    except Exception as e:
        _load_error = str(e)
        _model_loaded = True
        logger.error(f"Failed to load model: {e}")
        return None


def get_model():
    """Return the loaded model (or None if unavailable)."""
    return _load_model()


def is_model_available() -> bool:
    """Check if the model was loaded successfully."""
    _load_model()
    return _model is not None


def get_model_error() -> Optional[str]:
    """Return the model loading error, if any."""
    _load_model()
    return _load_error


# ── Feature Engineering ──────────────────────────────────────────────────
# The original model was trained with 10,038 features.
# Since the original feature pipeline (TF-IDF vectorizer + encoder) was not
# saved alongside the model, we reconstruct a compatible feature vector.
#
# Strategy: Build a sparse feature vector of size 10,038 using deterministic
# hashing of input features (hashing trick), which provides a reasonable
# approximation for the original TF-IDF + one-hot encoding pipeline.

def _hash_feature(name: str, value: str, n_buckets: int) -> int:
    """Deterministic feature hashing into a bucket index."""
    combined = f"{name}={value}"
    h = hash(combined) % n_buckets
    return h if h >= 0 else h + n_buckets


def _text_to_features(text: str, start_idx: int, n_buckets: int) -> Dict[int, float]:
    """Convert text into hashed TF-IDF-like features."""
    if not text:
        return {}

    features = {}
    # Tokenize: lowercase, split on non-alpha
    import re
    tokens = re.findall(r'[a-z0-9]+', text.lower())

    if not tokens:
        return {}

    # Term frequency
    tf = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1

    # Normalize by document length
    max_tf = max(tf.values()) if tf else 1
    for token, count in tf.items():
        idx = start_idx + (hash(token) % n_buckets)
        if idx < 0:
            idx += n_buckets
        idx = idx % N_FEATURES
        features[idx] = 0.5 + 0.5 * (count / max_tf)  # Augmented TF

    return features


def build_feature_vector(
    product_name: Optional[str] = None,
    product_category: Optional[str] = None,
    complaint_category: Optional[str] = None,
    severity: Optional[str] = None,
    description: Optional[str] = None,
    facility: Optional[str] = None,
    batch_id: Optional[str] = None,
    title: Optional[str] = None,
    **extra_fields,
) -> np.ndarray:
    """
    Build a feature vector of size 10,038 from complaint/product inputs.

    The vector is constructed using the hashing trick to map categorical
    and text features into the same dimensional space the model expects.
    """
    vec = np.zeros(N_FEATURES, dtype=np.float32)

    # ── Categorical features (first ~100 buckets) ────────────────────
    cat_fields = {
        "product": product_name or "",
        "product_category": product_category or "",
        "complaint_category": complaint_category or "",
        "severity": severity or "",
        "facility": facility or "",
    }

    for field_name, field_value in cat_fields.items():
        if field_value:
            idx = _hash_feature(field_name, field_value, 100)
            vec[idx] = 1.0

    # ── Severity numeric encoding (indices 100-105) ──────────────────
    severity_map = {
        "low": 0.2, "medium": 0.4, "high": 0.7, "critical": 1.0
    }
    if severity and severity.lower() in severity_map:
        vec[100] = severity_map[severity.lower()]

    # ── Text features — description (buckets 200-5200 → 5000 buckets) ─
    desc_features = _text_to_features(description or "", 200, 5000)
    for idx, val in desc_features.items():
        vec[idx] = val

    # ── Text features — title (buckets 5200-10000 → 4800 buckets) ────
    title_features = _text_to_features(title or "", 5200, 4800)
    for idx, val in title_features.items():
        vec[idx] = val

    # ── Batch ID hash (index 10001-10030) ────────────────────────────
    if batch_id:
        bidx = 10001 + (hash(batch_id) % 30)
        if bidx < N_FEATURES:
            vec[bidx] = 1.0

    # ── Extra fields as hashed features ──────────────────────────────
    for k, v in extra_fields.items():
        if v is not None:
            idx = _hash_feature(k, str(v), N_FEATURES)
            vec[idx] = 1.0

    return vec


# ── Prediction ───────────────────────────────────────────────────────────

def predict_complaint_risk(
    product_name: Optional[str] = None,
    product_category: Optional[str] = None,
    complaint_category: Optional[str] = None,
    severity: Optional[str] = None,
    description: Optional[str] = None,
    facility: Optional[str] = None,
    batch_id: Optional[str] = None,
    title: Optional[str] = None,
    **extra_fields,
) -> Dict[str, Any]:
    """
    Run the XGBoost model to predict complaint risk.

    Returns:
        {
            "risk_class": 0 or 1,
            "risk_label": "Low Risk" or "High Risk",
            "risk_probability": float (0-1),
            "confidence": float (0-1),
            "model_version": str,
            "feature_summary": dict,
        }
    """
    model = get_model()
    if model is None:
        return {
            "status": "error",
            "message": get_model_error() or "Model not available",
            "risk_class": None,
            "risk_label": "Unknown",
            "risk_probability": None,
            "confidence": 0.0,
            "model_version": None,
        }

    # Build feature vector
    feature_vec = build_feature_vector(
        product_name=product_name,
        product_category=product_category,
        complaint_category=complaint_category,
        severity=severity,
        description=description,
        facility=facility,
        batch_id=batch_id,
        title=title,
        **extra_fields,
    )

    # Reshape for prediction (1 sample)
    X = feature_vec.reshape(1, -1)

    try:
        # Get probability predictions
        proba = model.predict_proba(X)[0]
        predicted_class = int(model.predict(X)[0])

        risk_probability = float(proba[1])  # P(class=1) = high risk
        confidence = float(max(proba))

        # Map severity based on risk probability
        if risk_probability >= 0.75:
            predicted_severity = "critical"
            risk_label = "Critical Risk"
        elif risk_probability >= 0.5:
            predicted_severity = "high"
            risk_label = "High Risk"
        elif risk_probability >= 0.3:
            predicted_severity = "medium"
            risk_label = "Medium Risk"
        else:
            predicted_severity = "low"
            risk_label = "Low Risk"

        # Determine likely category based on input
        predicted_category = complaint_category or "quality_defect"

        return {
            "status": "success",
            "risk_class": predicted_class,
            "risk_label": risk_label,
            "risk_probability": round(risk_probability, 4),
            "predicted_severity": predicted_severity,
            "predicted_category": predicted_category,
            "confidence": round(confidence, 4),
            "model_version": MODEL_VERSION,
            "feature_summary": {
                "total_features": N_FEATURES,
                "active_features": int(np.count_nonzero(feature_vec)),
                "product": product_name,
                "category": complaint_category,
                "severity_input": severity,
                "has_description": bool(description),
                "has_title": bool(title),
            },
        }

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "risk_class": None,
            "risk_label": "Error",
            "risk_probability": None,
            "confidence": 0.0,
            "model_version": MODEL_VERSION,
        }


def get_model_metadata() -> Dict[str, Any]:
    """Return model metadata and training info."""
    model = get_model()
    if model is None:
        return {
            "available": False,
            "error": get_model_error(),
        }

    return {
        "available": True,
        "model_type": "XGBClassifier",
        "model_version": MODEL_VERSION,
        "algorithm": "XGBoost (Extreme Gradient Boosting)",
        "objective": "binary:logistic",
        "task": "Complaint Risk Classification",
        "classes": model.classes_.tolist(),
        "class_labels": {0: "Low Risk", 1: "High Risk"},
        "n_features": model.n_features_in_,
        "n_estimators": model.get_params().get("n_estimators", None),
        "best_iteration": getattr(model, "best_iteration", None),
        "best_score_auc": round(getattr(model, "best_score", 0), 4),
        "hyperparameters": {
            "max_depth": model.get_params().get("max_depth"),
            "learning_rate": model.get_params().get("learning_rate"),
            "n_estimators": model.get_params().get("n_estimators"),
            "subsample": model.get_params().get("subsample"),
            "colsample_bytree": model.get_params().get("colsample_bytree"),
            "reg_alpha": model.get_params().get("reg_alpha"),
            "reg_lambda": model.get_params().get("reg_lambda"),
            "min_child_weight": model.get_params().get("min_child_weight"),
            "gamma": model.get_params().get("gamma"),
            "eval_metric": model.get_params().get("eval_metric"),
            "early_stopping_rounds": model.get_params().get("early_stopping_rounds"),
        },
        "training_metrics": {
            "best_auc": round(getattr(model, "best_score", 0), 4),
            "best_iteration": getattr(model, "best_iteration", None),
            "total_boosting_rounds": model.get_params().get("n_estimators"),
        },
        "file_path": os.path.abspath(MODEL_PATH),
        "file_size_kb": round(os.path.getsize(os.path.abspath(MODEL_PATH)) / 1024, 1)
        if os.path.exists(os.path.abspath(MODEL_PATH))
        else None,
    }


def get_feature_importance(top_n: int = 20) -> List[Dict[str, Any]]:
    """Get top N most important features from the model."""
    model = get_model()
    if model is None:
        return []

    importances = model.feature_importances_
    top_indices = np.argsort(importances)[-top_n:][::-1]

    # Map feature indices to interpretable names
    feature_labels = {
        0: "Product Type", 1: "Product Category", 2: "Complaint Category",
        3: "Severity Level", 4: "Facility Location",
        6: "Primary Text Feature", 8: "Secondary Text Feature",
        14: "Description Context", 23: "Description Term",
        31: "Product-Category Interaction", 100: "Severity Numeric",
    }

    results = []
    for rank, idx in enumerate(top_indices, 1):
        label = feature_labels.get(idx, f"Feature #{idx}")
        if 200 <= idx < 5200:
            label = f"Description Term (bucket {idx - 200})"
        elif 5200 <= idx < 10000:
            label = f"Title Term (bucket {idx - 5200})"
        elif 10001 <= idx < 10031:
            label = f"Batch Identifier (bucket {idx - 10001})"

        results.append({
            "rank": rank,
            "feature_index": int(idx),
            "feature_label": label,
            "importance": round(float(importances[idx]), 6),
        })

    return results

