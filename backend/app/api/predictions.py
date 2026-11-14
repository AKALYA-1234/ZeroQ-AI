from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_admin
from app.ml.model_service import (
    is_model_available, get_model_metadata, get_feature_importance,
    predict_complaint_risk, get_model_error, MODEL_VERSION,
)

router = APIRouter()

@router.get("/status")
def get_model_status(current_user=Depends(get_current_admin)):
    metadata = get_model_metadata()
    return {
        "status": "active" if metadata.get("available") else "no_model",
        "model_available": metadata.get("available", False),
        "model_version": MODEL_VERSION if metadata.get("available") else None,
        "model_type": metadata.get("model_type"),
        "algorithm": metadata.get("algorithm"),
        "n_features": metadata.get("n_features"),
        "best_auc": metadata.get("training_metrics", {}).get("best_auc"),
        "error": get_model_error() if not metadata.get("available") else None,
    }


@router.post("/predict")
def predict(input_data: dict, current_user=Depends(get_current_admin)):
    if not is_model_available():
        return {
            "status": "unavailable",
            "message": get_model_error() or "Model not loaded.",
            "prediction": None,
        }

    result = predict_complaint_risk(
        product_name=input_data.get("product_name"),
        product_category=input_data.get("product_category"),
        complaint_category=input_data.get("category"),
        severity=input_data.get("severity"),
        description=input_data.get("description"),
        facility=input_data.get("facility"),
        batch_id=input_data.get("batch_id"),
        title=input_data.get("title"),
    )

    return {
        "status": result.get("status", "error"),
        "prediction": result,
    }


@router.get("/model-metadata")
def get_metadata(current_user=Depends(get_current_admin)):
    return get_model_metadata()


@router.get("/feature-importance")
def get_importance(top_n: int = 20, current_user=Depends(get_current_admin)):
    return {
        "features": get_feature_importance(top_n=top_n),
        "model_version": MODEL_VERSION if is_model_available() else None,
    }
