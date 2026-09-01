"""
GET /api/v1/products and GET /api/v1/products/{id}. Spec §2 — read-only,
no ordering logic here, that's orders.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.db.session import get_db_session

router = APIRouter(prefix="/api/v1/products", tags=["products"])


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    price_cents: int
    stock_qty: int

    model_config = {"from_attributes": True}  # lets Pydantic read straight off the ORM object


@router.get("", response_model=list[ProductOut])
async def list_products(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Product).order_by(Product.id).limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, session: AsyncSession = Depends(get_db_session)):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product
