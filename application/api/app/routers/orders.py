"""
POST /api/v1/orders and GET /api/v1/orders/{order_ref}. Spec §2 — the one
place in the whole app with a transaction, a row lock, and a real
business-rule rejection.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.db.models import Order, OrderItem, Product
from app.db.session import get_db_session

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


class OrderItemIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)


class OrderCreateIn(BaseModel):
    items: list[OrderItemIn]


class OrderItemOut(BaseModel):
    product_id: int
    qty: int
    unit_price_cents: int

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    order_ref: str
    status: str
    total_cents: int
    items: list[OrderItemOut]

    model_config = {"from_attributes": True}


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(body: OrderCreateIn, session: AsyncSession = Depends(get_db_session)):
    if not body.items:
        raise HTTPException(status_code=400, detail="order must contain at least one item")

    requested_ids = [item.product_id for item in body.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(status_code=400, detail="duplicate product_id in one order")

    # SELECT ... FOR UPDATE, per spec §2: locks these specific product rows
    # for the rest of this transaction. If two orders race for the same
    # product at the same instant, the second one waits here until the
    # first commits or rolls back — that's what makes the stock check
    # below actually trustworthy instead of a race condition.
    result = await session.execute(
        select(Product).where(Product.id.in_(requested_ids)).with_for_update()
    )
    products_by_id = {p.id: p for p in result.scalars().all()}

    missing = [pid for pid in requested_ids if pid not in products_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"product(s) not found: {missing}")

    for item in body.items:
        product = products_by_id[item.product_id]
        if product.stock_qty < item.qty:
            # Deliberately 409, not 400: the request is well-formed, it's
            # the current state of the world that makes it impossible.
            # Nothing is written — the transaction hasn't committed
            # anything yet, so stock is untouched on this path.
            raise HTTPException(
                status_code=409,
                detail=(
                    f"insufficient stock for product_id={item.product_id}: "
                    f"requested {item.qty}, available {product.stock_qty}"
                ),
            )

    order_items = []
    total_cents = 0
    for item in body.items:
        product = products_by_id[item.product_id]
        product.stock_qty -= item.qty
        line_total = product.price_cents * item.qty
        total_cents += line_total
        order_items.append(
            OrderItem(
                product_id=product.id,
                qty=item.qty,
                unit_price_cents=product.price_cents,  # captured now, not joined later
            )
        )

    order = Order(order_ref=str(ULID()), status="created", total_cents=total_cents)
    order.items = order_items  # type: ignore[attr-defined]  # see relationship note below
    session.add(order)
    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order


@router.get("/{order_ref}", response_model=OrderOut)
async def get_order(order_ref: str, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Order).where(Order.order_ref == order_ref))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    await session.refresh(order, attribute_names=["items"])
    return order
