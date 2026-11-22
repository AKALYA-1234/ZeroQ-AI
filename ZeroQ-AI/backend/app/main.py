from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import logging
import threading
from app.core.config import settings
from app.database.base import Base
from app.database.connection import engine
from app.database.migrations import apply_additive_migrations

# Import all models to register them with SQLAlchemy
from app.models import user, product, complaint, investigation, corrective_action, notification, intelligence as intelligence_models

# Import routers
from app.api import auth, customers, products, complaints, admin, predictions, intelligence
from app.ml.model_service import is_model_available
from app.intelligence.realtime import broker

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
    try:
        from app.api.intelligence import recover_missing_analyses
        recover_missing_analyses(SessionLocal.kw["bind"])
    except Exception:
        logging.getLogger(__name__).exception("Analysis recovery sweep failed")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        Base.metadata.create_all(bind=engine)
        apply_additive_migrations(engine)
        # Pre-cache model
        is_model_available()
    except Exception as e:
        print(f"Startup warning: {e}")
    # Warm the issue classifier + historical index off the request path.
    threading.Thread(target=_warm_issue_intelligence, daemon=True).start()
    broker.bind_loop(asyncio.get_running_loop())
    bus_task = asyncio.create_task(broker.bus.listen()) if hasattr(broker.bus, "listen") else None
    yield
    if bus_task:
        bus_task.cancel()

app = FastAPI(
    title="ZeroQ AI API",
    description="ABT-CPD Zero Customer Complaint: AI-Based Manufacturing Quality Analytics",
    version="1.0.0",
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url="/api/redoc" if settings.docs_enabled else None,
    openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan
)

# Attachments are NOT publicly mounted; they are served by the authenticated
# /api/complaints/{id}/attachments/{attachment_id} endpoint.

# Cross-origin access is opt-in (CORS_ORIGINS); the default is same-origin via the frontend proxy.
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])

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
