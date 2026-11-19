from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
import threading
from app.core.config import settings
from app.database.base import Base
from app.database.connection import engine

# Import all models to register them with SQLAlchemy
from app.models import user, product, complaint, investigation, corrective_action, notification, intelligence as intelligence_models

# Import routers
from app.api import auth, customers, products, complaints, admin, predictions, intelligence
from app.ml.model_service import is_model_available

def _warm_issue_intelligence():
    from app.database.connection import SessionLocal
    from app.intelligence.learning import get_classifier
    from app.intelligence.retrieval import get_index
    db = SessionLocal()
    try:
        get_classifier(db)
        get_index(db)
    except Exception as e:  # analysis still works lazily on first request
        logging.getLogger(__name__).warning("Issue-intelligence warm-up failed: %s", e)
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        Base.metadata.create_all(bind=engine)
        # Pre-cache model
        is_model_available()
    except Exception as e:
        print(f"Startup warning: {e}")
    # Warm the issue classifier + historical index off the request path.
    threading.Thread(target=_warm_issue_intelligence, daemon=True).start()
    yield

app = FastAPI(
    title="ZeroQ AI API",
    description="ABT-CPD Zero Customer Complaint: AI-Based Manufacturing Quality Analytics",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Mount uploads
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(customers.router, prefix="/api/customer", tags=["Customer"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["ML Predictions"])
app.include_router(intelligence.router, prefix="/api/admin/intelligence", tags=["Issue Intelligence"])
app.include_router(intelligence.ws_router, tags=["Real-time"])

@app.get("/")
def root():
    return {"message": "ZeroQ AI API", "version": "1.0.0", "docs": "/api/docs"}

@app.get("/api/health")
def health():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}
