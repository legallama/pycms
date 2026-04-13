from datetime import datetime, timezone
from ..extensions import db
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

class Product(db.Model):
    __tablename__ = "shop_products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(db.Text, default="")
    price: Mapped[float] = mapped_column(db.Float, default=0.0)
    inventory: Mapped[int] = mapped_column(db.Integer, default=0)
    image_url: Mapped[str] = mapped_column(db.String(512), default="")
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    product_type: Mapped[Optional[str]] = mapped_column(db.String(50), default="physical") 
    options_json: Mapped[Optional[str]] = mapped_column(db.Text, default="[]") 
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Order(db.Model):
    __tablename__ = "shop_orders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(db.Integer, db.ForeignKey("users.id"))
    customer_name: Mapped[Optional[str]] = mapped_column(db.String(255))
    customer_email: Mapped[str] = mapped_column(db.String(255), nullable=False)
    shipping_address: Mapped[Optional[str]] = mapped_column(db.Text)
    shipping_city: Mapped[Optional[str]] = mapped_column(db.String(100))
    shipping_zip: Mapped[Optional[str]] = mapped_column(db.String(20))
    total_amount: Mapped[float] = mapped_column(db.Float, nullable=False)
    status: Mapped[str] = mapped_column(db.String(50), default="pending") # pending, paid, shipped, cancelled
    payment_gateway: Mapped[Optional[str]] = mapped_column(db.String(50)) # stripe, paypal, paddle
    gateway_order_id: Mapped[Optional[str]] = mapped_column(db.String(255))
    items_json: Mapped[Optional[str]] = mapped_column(db.Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
