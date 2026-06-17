"""SQLAlchemy ORM models for Customer, Order, and Refund."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    created_at = Column(
        DateTime, nullable=False, server_default=text("NOW()")
    )

    # Relationships
    orders = relationship("Order", back_populates="customer", lazy="noload")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', email='{self.email}')>"


class Order(Base):
    """Order model."""
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="completed")
    order_date = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, nullable=False, server_default=text("NOW()")
    )

    # Relationships
    customer = relationship("Customer", back_populates="orders", lazy="noload")
    refund = relationship("Refund", back_populates="order", uselist=False, lazy="noload")

    # Indexes for analytics performance
    __table_args__ = (
        Index("idx_orders_customer_id", "customer_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_order_date", "order_date"),
        Index("idx_orders_customer_amount", "customer_id", "total_amount"),
        Index("idx_orders_status_amount", "status", "total_amount"),
    )

    def __repr__(self):
        return f"<Order(id={self.id}, amount={self.total_amount}, status='{self.status}')>"


class Refund(Base):
    """Refund model."""
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    refund_amount = Column(Float, nullable=False)
    reason = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default="completed")
    refund_date = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, nullable=False, server_default=text("NOW()")
    )

    # Relationships
    order = relationship("Order", back_populates="refund", lazy="noload")

    # Indexes
    __table_args__ = (
        Index("idx_refunds_order_id", "order_id"),
        Index("idx_refunds_status", "status"),
        Index("idx_refunds_status_amount", "status", "refund_amount"),
    )

    def __repr__(self):
        return f"<Refund(id={self.id}, amount={self.refund_amount}, status='{self.status}')>"
