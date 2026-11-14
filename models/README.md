# Trained Models

Place trained ML model artifacts here.

## Expected Artifacts

- `xgboost_model.joblib` or `xgboost_model.pkl`
- `logistic_regression_model.joblib`
- `preprocessor.joblib`
- `feature_names.json`
- `model_metrics.json`

The backend will attempt to load these on startup. If not present, the AI Prediction Center will show "Model Validation Pending".

