"""
The three database tables this app uses. See spec §2 for the full reasoning.

Nothing in this file talks to a real database yet — it only describes the
*shape* of the data. The actual connection comes in the next step.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_products_price_nonneg"),
        CheckConstraint("stock_qty >= 0", name="ck_products_stock_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    price_cents: Mapped[int]
    stock_qty: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_ref: Mapped[str] = mapped_column(unique=True)  # ULID, the public handle
    status: Mapped[str]  # 'created' | 'rejected'
    total_cents: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Python-side only — lets code write order.items instead of a separate
    # query. Doesn't add a column or need a migration; it just rides on the
    # order_id foreign key that OrderItem already has.
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_items_qty_positive"),
        UniqueConstraint("order_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int]
    unit_price_cents: Mapped[int]  # price captured at order time, not joined later

    order: Mapped["Order"] = relationship(back_populates="items")
