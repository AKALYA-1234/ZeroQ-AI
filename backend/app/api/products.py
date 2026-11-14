from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.product import Product
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/")
@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).all()
    return [{"id": p.id, "product_id": p.product_id, "name": p.name, "category": p.category} for p in products]

@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")
    return {"id": product.id, "product_id": product.product_id, "name": product.name, "category": product.category, "description": product.description}
