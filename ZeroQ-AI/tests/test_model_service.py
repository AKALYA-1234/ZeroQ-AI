import pytest
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.ml.model_service import (
    is_model_available,
    get_model_metadata,
    get_threshold,
    get_feature_importance,
    predict_batch,
    predict_from_features,
    evaluate_nlp_query,
    get_model,
    _init_model_service,
    MODEL_DIR
)

def test_model_availability_and_metadata():
    assert is_model_available() is True
    meta = get_model_metadata()
    assert meta["available"] is True
    assert meta["n_features_in"] == 10038
    assert meta["threshold"] == pytest.approx(0.325, abs=0.005)
    assert meta["raw_features_count"] == 54

def test_feature_importance():
    fi = get_feature_importance(top_n=10)
    assert len(fi) == 10
    assert "importance" in fi[0]
    assert "feature_name" in fi[0]
    # Check that highest importance is process deviation flag
    assert "process deviation" in fi[0]["feature_name"].lower() or "flag" in fi[0]["feature_name"].lower()

def test_train_serve_skew_reproduction():
    """
    Guard against train/serve skew: runs the preprocessor and model on test_raw.csv
    and verifies that it reproduces saved test_probabilities.npy and test_predictions.npy
    within numerical tolerance (0.0001).
    """
    import joblib
    _init_model_service()
    model = get_model()
    
    preprocessor_path = os.path.join(MODEL_DIR, "model_ready_data", "preprocessor.joblib")
    test_raw_path = os.path.join(MODEL_DIR, "model_ready_data", "test_raw.csv")
    saved_probs_path = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "test_probabilities.npy")
    saved_preds_path = os.path.join(MODEL_DIR, "model_training", "final_xgboost", "test_predictions.npy")

    assert os.path.exists(test_raw_path), "test_raw.csv missing"
    assert os.path.exists(saved_probs_path), "test_probabilities.npy missing"

    test_raw = pd.read_csv(test_raw_path)
    X_raw = test_raw.drop(columns=["complaint_within_90_days"])
    prep = joblib.load(preprocessor_path)

    # Transform using preprocessor
    X_trans = prep.transform(X_raw)
    assert X_trans.shape == (3571, 10038)

    # Predict probabilities with runtime model
    runtime_probs = model.predict_proba(X_trans)[:, 1]
    saved_probs = np.load(saved_probs_path)

    max_prob_diff = float(np.max(np.abs(runtime_probs - saved_probs)))
    print(f"Max train/serve probability skew: {max_prob_diff}")
    assert max_prob_diff < 1e-4, f"Train/serve skew detected: max diff = {max_prob_diff}"

    # Verify binary predictions at threshold
    threshold = get_threshold()
    runtime_preds = (runtime_probs >= threshold).astype(int)
    saved_preds = np.load(saved_preds_path)

    agreement = float(np.mean(runtime_preds == saved_preds))
    assert agreement >= 0.999, f"Prediction mismatch: agreement = {agreement}"

def test_predict_batch():
    # Test batch BAT000004
    res = predict_batch("BAT000004")
    assert res["status"] == "success"
    assert "complaint_probability" in res
    assert 0.0 <= res["complaint_probability"] <= 1.0
    assert "risk_level" in res
    assert "explanation" in res
    assert len(res["contributing_factors"]) > 0

def test_predict_from_features():
    inputs = {
        "product_name": "Fruit Jam",
        "facility_name": "Pune Manufacturing Unit",
        "production_shift": "Night",
        "process_temperature_c": 128.5,
        "process_deviation_flag": 1
    }
    res = predict_from_features(inputs)
    assert res["status"] == "success"
    assert "complaint_probability" in res
    assert len(res["explanation"]) > 20
    assert "risk_level" in res

def test_evaluate_nlp_query():
    query = "Predict defect risk for Classic Biscuits in Pune facility on Night shift with temperature 135C"
    res = evaluate_nlp_query(query)
    assert res["status"] == "success"
    assert res["parse_confidence"] >= 0.80
    assert res["prediction"] in [0, 1]
    assert "explanation" in res
    assert len(res["clues_extracted"]) >= 3
