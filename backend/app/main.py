from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings
from app.database.base import Base
from app.database.connection import engine

# Import all models to register them with SQLAlchemy
from app.models import user, product, complaint, investigation, corrective_action, notification

# Import routers
from app.api import auth, customers, products, complaints, admin, predictions

app = FastAPI(
    title="ZeroQ AI API",
    description="ABT-CPD Zero Customer Complaint: AI-Based Manufacturing Quality Analytics",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
async def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not create tables: {e}")

# Mount uploads
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(customers.router, prefix="/api/customer", tags=["Customer"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["ML Predictions"])

@app.get("/")
def root():
    return {"message": "ZeroQ AI API", "version": "1.0.0", "docs": "/api/docs"}

@app.get("/api/health")
def health():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}
