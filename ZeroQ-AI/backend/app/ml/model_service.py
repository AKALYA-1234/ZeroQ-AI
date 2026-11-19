"""
ZeroQ AI — Production Machine Learning Model Service
Loads and caches the trained XGBoost binary classification model,
preprocessor, decision threshold, and feature importance artifacts.
Provides batch risk prediction, hypothetical forward-looking condition scoring,
and natural language query parsing & evaluation.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger(__name__)

# ── Paths to Trained Artifacts & Data ─────────────────────────────────────
# Application trained model
APP_MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "trained", "final_xgboost_model.joblib")
)
# Model training workspace artifacts
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "Model"))
PREPROCESSOR_PATH = os.path.join(MODEL_DIR, "model_ready_data", "preprocessor.joblib")
THRESHOLD_PATH = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "final_threshold.joblib")
FEATURE_NAMES_PATH = os.path.join(MODEL_DIR, "model_ready_data", "transformed_feature_names.csv")
IMPORTANCE_PATH = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "feature_importance.csv")
METRICS_PATH = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "final_model_metrics.csv")
PRE_DISPATCH_CSV = os.path.join(MODEL_DIR, "feature_engineered_data", "batch_features_pre_dispatch.csv")
TRAIN_RAW_CSV = os.path.join(MODEL_DIR, "model_ready_data", "train_raw.csv")

MODEL_VERSION = "xgboost-v1.0-final"
DEFAULT_THRESHOLD = 0.325
N_FEATURES = 10038

# ── Singleton Cache ───────────────────────────────────────────────────────
_model = None
_preprocessor = None
_threshold = DEFAULT_THRESHOLD
_feature_names = None
_feature_importance = None
_training_metrics = {}
_baseline_defaults = {}
_pre_dispatch_cache = None
_model_loaded = False
_load_error: Optional[str] = None


def _init_model_service():
    """Load and cache model artifacts into memory once at startup."""
    global _model, _preprocessor, _threshold, _feature_names
    global _feature_importance, _training_metrics, _baseline_defaults
    global _pre_dispatch_cache, _model_loaded, _load_error

    if _model_loaded:
        return _model

    logger.info(f"Initializing ZeroQ AI Model Service from {APP_MODEL_PATH}...")
    try:
        # 1. Load trained XGBoost model
        if not os.path.exists(APP_MODEL_PATH):
            # Fallback to Model directory if app path not found
            fallback = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "final_xgboost_model.joblib")
            if os.path.exists(fallback):
                _model = joblib.load(fallback)
            else:
                raise FileNotFoundError(f"Trained model artifact not found at {APP_MODEL_PATH}")
        else:
            _model = joblib.load(APP_MODEL_PATH)

        # 2. Load Preprocessor
        if os.path.exists(PREPROCESSOR_PATH):
            _preprocessor = joblib.load(PREPROCESSOR_PATH)
            # Patch cross-version scikit-learn attribute changes (e.g. 1.7.x vs 1.9.x)
            for _, trans, _ in getattr(_preprocessor, "transformers_", []):
                if hasattr(trans, "steps"):
                    for _, step in trans.steps:
                        if hasattr(step, "_fit_dtype") and not hasattr(step, "_fill_dtype"):
                            step._fill_dtype = step._fit_dtype
                        elif hasattr(step, "_fill_dtype") and not hasattr(step, "_fit_dtype"):
                            step._fit_dtype = step._fill_dtype
        else:
            raise FileNotFoundError(f"Preprocessor not found at {PREPROCESSOR_PATH}")

        # 3. Load Decision Threshold
        if os.path.exists(THRESHOLD_PATH):
            _threshold = float(joblib.load(THRESHOLD_PATH))
        else:
            _threshold = DEFAULT_THRESHOLD

        # 4. Load Transformed Feature Names & Importance
        if os.path.exists(FEATURE_NAMES_PATH) and os.path.exists(IMPORTANCE_PATH):
            fnames_df = pd.read_csv(FEATURE_NAMES_PATH)
            imp_df = pd.read_csv(IMPORTANCE_PATH)
            merged = imp_df.merge(fnames_df, left_on="feature_index", right_on="Feature_Index", how="left")
            _feature_importance = merged.sort_values(by="importance", ascending=False)
            _feature_names = fnames_df["Feature_Name"].tolist()

        # 5. Load Training Metrics
        if os.path.exists(METRICS_PATH):
            m_df = pd.read_csv(METRICS_PATH)
            if len(m_df) > 0:
                _training_metrics = m_df.iloc[0].to_dict()

        # 6. Precompute Baseline Feature Defaults for free-form queries
        if os.path.exists(TRAIN_RAW_CSV):
            tr_df = pd.read_csv(TRAIN_RAW_CSV, nrows=5000)
            feat_df = tr_df.drop(columns=["complaint_within_90_days"], errors="ignore")
            num_meds = feat_df.select_dtypes(include=[np.number]).median().to_dict()
            cat_modes = feat_df.select_dtypes(include=["object"]).mode().iloc[0].to_dict()
            _baseline_defaults = {**num_meds, **cat_modes}

        # 7. Index pre-dispatch batch features for fast O(1) batch lookup
        if os.path.exists(PRE_DISPATCH_CSV):
            pdf = pd.read_csv(PRE_DISPATCH_CSV)
            # Store subset of columns needed for preprocessor
            expected_cols = list(_preprocessor.feature_names_in_)
            cols_to_keep = ["batch_id"] + [c for c in expected_cols if c in pdf.columns]
            _pre_dispatch_cache = pdf[cols_to_keep].set_index("batch_id")

        _model_loaded = True
        _load_error = None
        logger.info(
            f"ZeroQ AI ML Service initialized successfully. "
            f"Model: {type(_model).__name__}, Features: {_model.n_features_in_}, "
            f"Threshold: {_threshold:.4f}, Baseline Features: {len(_baseline_defaults)}"
        )
        return _model

    except Exception as e:
        _load_error = str(e)
        _model_loaded = True
        logger.error(f"Failed to initialize ML Service: {e}", exc_info=True)
        return None


def get_model():
    """Return the cached XGBoost model."""
    return _init_model_service()


def is_model_available() -> bool:
    """Check if the model and preprocessor are active."""
    _init_model_service()
    return _model is not None and _preprocessor is not None


def get_model_error() -> Optional[str]:
    """Return initialization error message, if any."""
    _init_model_service()
    return _load_error


def get_threshold() -> float:
    """Return optimal decision threshold (default 0.325)."""
    _init_model_service()
    return _threshold


def get_model_metadata() -> Dict[str, Any]:
    """Return comprehensive metadata about the model, preprocessor, and metrics."""
    _init_model_service()
    return {
        "available": is_model_available(),
        "model_version": MODEL_VERSION,
        "model_type": "Binary Classifier (XGBClassifier)",
        "algorithm": "Gradient Boosted Decision Trees (XGBoost)",
        "n_features_in": _model.n_features_in_ if _model else N_FEATURES,
        "raw_features_count": len(_preprocessor.feature_names_in_) if _preprocessor else 54,
        "threshold": _threshold,
        "classes": _model.classes_.tolist() if _model and hasattr(_model, "classes_") else [0, 1],
        "target_definition": "complaint_within_90_days (1=Complaint within 90 days of dispatch, 0=Zero complaints)",
        "training_metrics": _training_metrics,
        "error": _load_error
    }


def get_feature_importance(top_n: int = 20) -> List[Dict[str, Any]]:
    """Return top global feature importances with descriptive names."""
    _init_model_service()
    if _feature_importance is None or len(_feature_importance) == 0:
        return []
    
    top_df = _feature_importance.head(top_n)
    results = []
    for _, row in top_df.iterrows():
        raw_name = str(row.get("Feature_Name", f"feature_{row['feature_index']}"))
        clean_name = raw_name.replace("categorical__", "").replace("numeric__", "").replace("_", " ")
        results.append({
            "feature_index": int(row["feature_index"]),
            "feature_name": clean_name,
            "raw_feature_name": raw_name,
            "importance": round(float(row["importance"]), 5)
        })
    return results


def _build_feature_row(user_inputs: Dict[str, Any]) -> pd.DataFrame:
    """
    Constructs a 54-feature DataFrame matching the preprocessor schema.
    Applies baseline defaults for unspecified features.
    """
    _init_model_service()
    row = dict(_baseline_defaults)

    # Apply user provided fields
    if "units_produced" in user_inputs and user_inputs["units_produced"] is not None:
        row["units_produced"] = float(user_inputs["units_produced"])
    if "process_temperature_c" in user_inputs and user_inputs["process_temperature_c"] is not None:
        row["process_temperature_c"] = float(user_inputs["process_temperature_c"])
    if "ambient_humidity_pct" in user_inputs and user_inputs["ambient_humidity_pct"] is not None:
        row["ambient_humidity_pct"] = float(user_inputs["ambient_humidity_pct"])
    if "line_pressure_bar" in user_inputs and user_inputs["line_pressure_bar"] is not None:
        row["line_pressure_bar"] = float(user_inputs["line_pressure_bar"])
    if "sealing_temperature_c" in user_inputs and user_inputs["sealing_temperature_c"] is not None:
        row["sealing_temperature_c"] = float(user_inputs["sealing_temperature_c"])
    if "process_deviation_flag" in user_inputs and user_inputs["process_deviation_flag"] is not None:
        row["process_deviation_flag"] = int(user_inputs["process_deviation_flag"])
    if "supplier_quality_grade" in user_inputs and user_inputs["supplier_quality_grade"]:
        row["supplier_quality_grade"] = str(user_inputs["supplier_quality_grade"])
    if "production_shift" in user_inputs and user_inputs["production_shift"]:
        row["production_shift"] = str(user_inputs["production_shift"])
    if "product_name" in user_inputs and user_inputs["product_name"]:
        row["product_product_name"] = str(user_inputs["product_name"])
    if "product_category" in user_inputs and user_inputs["product_category"]:
        row["product_product_category"] = str(user_inputs["product_category"])
    if "facility_name" in user_inputs and user_inputs["facility_name"]:
        row["facility_facility_name"] = str(user_inputs["facility_name"])
    if "facility_state" in user_inputs and user_inputs["facility_state"]:
        row["facility_state"] = str(user_inputs["facility_state"])
    if "packaging_material_name" in user_inputs and user_inputs["packaging_material_name"]:
        row["packaging_material_name"] = str(user_inputs["packaging_material_name"])

    # Ensure all required preprocessor columns exist in the DataFrame
    expected_cols = list(_preprocessor.feature_names_in_)
    data = {c: [row.get(c, 0)] for c in expected_cols}
    return pd.DataFrame(data)


def _compute_contributing_factors(X_trans_row, top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Identifies the key contributing features that drove the prediction
    for a specific transformed sample.
    """
    if _feature_importance is None:
        return []

    indices = X_trans_row.indices
    data = X_trans_row.data
    contributions = []

    for idx, val in zip(indices, data):
        # Match with feature importance
        imp_row = _feature_importance[_feature_importance["feature_index"] == idx]
        if len(imp_row) > 0:
            imp = float(imp_row["importance"].values[0])
            fname = str(imp_row["Feature_Name"].values[0])
            # Only consider meaningful non-zero contributions
            clean_name = fname.replace("categorical__", "").replace("numeric__", "").replace("_", " ")
            contributions.append({
                "feature_index": int(idx),
                "feature_name": clean_name,
                "value": round(float(val), 2),
                "importance": round(imp, 5),
                "impact_score": round(imp * abs(val), 5)
            })

    contributions.sort(key=lambda x: x["importance"], reverse=True)
    return contributions[:top_n]


def _generate_explanation(prob: float, threshold: float, factors: List[Dict[str, Any]], context_type: str = "batch") -> str:
    """Generate a clear plain-language risk explanation."""
    pct = round(prob * 100, 1)
    thresh_pct = round(threshold * 100, 1)

    if prob >= threshold:
        risk_desc = f"ELEVATED RISK ({pct}% probability, exceeding the {thresh_pct}% intervention threshold)."
        action_advice = "Pre-dispatch quality quarantine and sealing verification recommended."
    elif prob >= 0.20:
        risk_desc = f"MODERATE RISK ({pct}% probability, below the {thresh_pct}% threshold)."
        action_advice = "Standard sampling inspection advised before release."
    else:
        risk_desc = f"LOW RISK ({pct}% probability, well below the {thresh_pct}% threshold)."
        action_advice = "Production conditions nominal; proceed with standard dispatch."

    factor_descriptions = []
    for f in factors[:3]:
        factor_descriptions.append(f"{f['feature_name']} (weight: {f['importance']})")

    drivers = ", ".join(factor_descriptions) if factor_descriptions else "nominal operating parameters"
    return f"{risk_desc} Key risk indicators influencing this evaluation: {drivers}. {action_advice}"


def predict_batch(batch_id: str) -> Dict[str, Any]:
    """
    Runs model prediction on a historical or active batch from the dataset.
    """
    _init_model_service()
    if not is_model_available():
        return {"status": "error", "message": _load_error or "Model not loaded"}

    # Look up batch in pre_dispatch cache
    batch_code = batch_id.strip().upper()
    if _pre_dispatch_cache is not None and batch_code in _pre_dispatch_cache.index:
        batch_row = _pre_dispatch_cache.loc[[batch_code]]
        # Match columns expected by preprocessor
        expected_cols = list(_preprocessor.feature_names_in_)
        aligned_df = batch_row[expected_cols]
    else:
        # Batch not in historical pre-dispatch CSV, use defaults with batch_id
        aligned_df = _build_feature_row({"batch_id": batch_code})

    X_trans = _preprocessor.transform(aligned_df)
    probs = _model.predict_proba(X_trans)[0]
    p_complaint = float(probs[1])
    is_high_risk = bool(p_complaint >= _threshold)
    
    factors = _compute_contributing_factors(X_trans[0])
    explanation = _generate_explanation(p_complaint, _threshold, factors, context_type="batch")

    severity = "critical" if p_complaint >= 0.50 else ("high" if is_high_risk else ("medium" if p_complaint >= 0.20 else "low"))

    return {
        "status": "success",
        "batch_id": batch_code,
        "prediction": 1 if is_high_risk else 0,
        "is_high_risk": is_high_risk,
        "predicted_severity": severity,
        "risk_level": "High" if is_high_risk else "Low",
        "complaint_probability": round(p_complaint, 4),
        "zero_complaint_probability": round(float(probs[0]), 4),
        "confidence": round(float(np.max(probs)), 4),
        "threshold": _threshold,
        "contributing_factors": factors,
        "explanation": explanation,
        "model_version": MODEL_VERSION
    }


def predict_from_features(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs model prediction on arbitrary user parameters,
    interpolating baseline historical medians for missing values.
    """
    _init_model_service()
    if not is_model_available():
        return {"status": "error", "message": _load_error or "Model not loaded"}

    df_row = _build_feature_row(inputs)
    X_trans = _preprocessor.transform(df_row)
    probs = _model.predict_proba(X_trans)[0]
    p_complaint = float(probs[1])
    is_high_risk = bool(p_complaint >= _threshold)

    factors = _compute_contributing_factors(X_trans[0])
    explanation = _generate_explanation(p_complaint, _threshold, factors, context_type="conditions")
    severity = "critical" if p_complaint >= 0.50 else ("high" if is_high_risk else ("medium" if p_complaint >= 0.20 else "low"))

    return {
        "status": "success",
        "prediction": 1 if is_high_risk else 0,
        "is_high_risk": is_high_risk,
        "predicted_severity": severity,
        "risk_level": "High" if is_high_risk else "Low",
        "complaint_probability": round(p_complaint, 4),
        "zero_complaint_probability": round(float(probs[0]), 4),
        "confidence": round(float(np.max(probs)), 4),
        "threshold": _threshold,
        "contributing_factors": factors,
        "explanation": explanation,
        "model_version": MODEL_VERSION
    }


def evaluate_nlp_query(query: str, user_id: Optional[int] = None, db_session = None) -> Dict[str, Any]:
    """
    End-to-end NLP query execution pipeline:
    1. Parse free-text into structured manufacturing parameters
    2. Handle missing or ambiguous fields with documented defaults
    3. Generate XGBoost model prediction
    4. Store query, parsed fields, and prediction in database
    5. Return prediction result + explanation
    """
    from app.ml.nlp_parser import parse_manufacturing_query
    from app.models.notification import ModelPrediction

    extracted, confidence, clues, assumed_defaults = parse_manufacturing_query(query)

    if confidence < 0.10 and not extracted:
        return {
            "status": "invalid_input",
            "message": (
                "Could not identify manufacturing quality entities in your query. "
                "Please specify a Batch ID (e.g. BAT000004), Product (e.g. Classic Biscuits), "
                "Manufacturing Facility (e.g. Pune Unit), or operating conditions (temperature, humidity, pressure)."
            ),
            "raw_query": query,
            "parsed_fields": {},
            "parse_confidence": 0.0
        }

    # Execute prediction: batch lookup or condition feature vector
    if "batch_id" in extracted:
        pred_result = predict_batch(extracted["batch_id"])
    else:
        pred_result = predict_from_features(extracted)

    if pred_result.get("status") != "success":
        return pred_result

    # Persist in Database if db_session is provided
    prediction_record_id = f"PRED-{datetime.utcnow().year}-{os.urandom(3).hex().upper()}"
    if db_session:
        try:
            db_record = ModelPrediction(
                prediction_id=prediction_record_id,
                model_version=MODEL_VERSION,
                raw_query=query,
                parsed_fields=extracted,
                parse_confidence=confidence,
                input_features=extracted,
                prediction_result=pred_result,
                confidence_score=str(pred_result.get("confidence")),
                explanation=pred_result.get("explanation"),
                created_by=user_id,
                created_at=datetime.utcnow()
            )
            db_session.add(db_record)
            db_session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist prediction record to DB: {e}")

    return {
        "status": "success",
        "prediction_id": prediction_record_id,
        "raw_query": query,
        "parsed_fields": extracted,
        "parse_confidence": confidence,
        "clues_extracted": clues,
        "assumed_defaults": assumed_defaults,
        "prediction": pred_result.get("prediction"),
        "risk_level": pred_result.get("risk_level"),
        "predicted_severity": pred_result.get("predicted_severity"),
        "complaint_probability": pred_result.get("complaint_probability"),
        "zero_complaint_probability": pred_result.get("zero_complaint_probability"),
        "confidence": pred_result.get("confidence"),
        "threshold": _threshold,
        "contributing_factors": pred_result.get("contributing_factors"),
        "explanation": pred_result.get("explanation"),
        "model_version": MODEL_VERSION,
        "created_at": datetime.utcnow().isoformat()
    }


def predict_complaint_risk(
    product_name: Optional[str] = None,
    product_category: Optional[str] = None,
    complaint_category: Optional[str] = None,
    severity: Optional[str] = None,
    description: Optional[str] = None,
    facility: Optional[str] = None,
    batch_id: Optional[str] = None,
    title: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper for existing API routes,
    redirecting to the production XGBoost model service.
    """
    if batch_id and str(batch_id).startswith("BAT"):
        return predict_batch(batch_id)

    inputs = {
        "product_name": product_name,
        "product_category": product_category,
        "facility_name": facility,
        "supplier_quality_grade": kwargs.get("supplier_quality_grade", "A"),
        "production_shift": kwargs.get("production_shift", "Morning")
    }
    return predict_from_features(inputs)
