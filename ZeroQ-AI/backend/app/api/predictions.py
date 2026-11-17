from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database.connection import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.ml.model_service import (
    is_model_available, get_model_metadata, get_feature_importance,
    predict_batch, predict_from_features, evaluate_nlp_query,
    get_model_error, MODEL_VERSION,
)

router = APIRouter()

class PredictionRequest(BaseModel):
    batch_id: Optional[str] = None
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    facility_name: Optional[str] = None
    production_shift: Optional[str] = None
    process_temperature_c: Optional[float] = None
    ambient_humidity_pct: Optional[float] = None
    line_pressure_bar: Optional[float] = None
    sealing_temperature_c: Optional[float] = None
    supplier_quality_grade: Optional[str] = None
    process_deviation_flag: Optional[int] = None
    packaging_material_name: Optional[str] = None

class NLPQueryRequest(BaseModel):
    query: str

@router.get("/status")
def get_model_status(current_user=Depends(get_current_user)):
    meta = get_model_metadata()
    return {
        "status": "active" if meta.get("available") else "no_model",
        "model_available": meta.get("available", False),
        "model_version": MODEL_VERSION if meta.get("available") else None,
        "model_type": meta.get("model_type"),
        "algorithm": meta.get("algorithm"),
        "n_features": meta.get("n_features_in"),
        "threshold": meta.get("threshold"),
        "training_metrics": meta.get("training_metrics", {}),
        "error": get_model_error() if not meta.get("available") else None,
    }


@router.post("/predict")
def predict(input_data: PredictionRequest, current_user=Depends(get_current_user)):
    if not is_model_available():
        raise HTTPException(status_code=503, detail=get_model_error() or "Model not loaded.")

    data_dict = input_data.model_dump(exclude_unset=True)
    if input_data.batch_id:
        result = predict_batch(input_data.batch_id)
    else:
        result = predict_from_features(data_dict)

    return {
        "status": result.get("status", "error"),
        "prediction": result,
    }


@router.post("/query")
def evaluate_query(
    body: NLPQueryRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluates free-text natural language query and returns prediction + explanation.
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return evaluate_nlp_query(body.query.strip(), user_id=current_user.id, db_session=db)


@router.get("/model-metadata")
def get_metadata(current_user=Depends(get_current_user)):
    return get_model_metadata()


@router.get("/feature-importance")
def get_importance(top_n: int = 20, current_user=Depends(get_current_user)):
    return {
        "features": get_feature_importance(top_n=top_n),
        "model_version": MODEL_VERSION if is_model_available() else None,
    }
