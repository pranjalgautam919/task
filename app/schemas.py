"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


# ─── Customer Schemas ───────────────────────────────────────────────────────

class CustomerBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


# ─── Order Schemas ───────────────────────────────────────────────────────────

class OrderBase(BaseModel):
    customer_id: UUID
    total_amount: float
    status: str = "completed"
    order_date: datetime


class OrderResponse(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


# ─── Refund Schemas ──────────────────────────────────────────────────────────

class RefundBase(BaseModel):
    order_id: UUID
    refund_amount: float
    reason: Optional[str] = None
    status: str = "completed"
    refund_date: datetime


class RefundResponse(RefundBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


# ─── Pagination ──────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    data: List[T]
    page: int
    page_size: int
    total_count: int
    total_pages: int


# ─── Analytics Schemas ───────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    """Summary of all key analytics metrics."""
    total_orders: int
    total_revenue: float
    total_refunds: int
    total_refund_amount: float
    net_revenue: float
    avg_order_value: float


class RepeatCustomerRevenue(BaseModel):
    """Revenue from repeat customers (customers with > 1 order)."""
    repeat_customer_count: int
    repeat_customer_revenue: float
    repeat_customer_percentage: float = Field(
        ..., description="Percentage of total revenue from repeat customers"
    )


class RevenueTrendPoint(BaseModel):
    """Single data point in revenue trend."""
    period: str
    order_count: int
    revenue: float


class RevenueTrends(BaseModel):
    """Revenue trends over time."""
    period_type: str = Field(..., description="daily or monthly")
    data: List[RevenueTrendPoint]


class TopCustomer(BaseModel):
    """Top customer by total spend."""
    customer_id: UUID
    customer_name: str
    customer_email: str
    total_orders: int
    total_spend: float


class TopCustomersResponse(BaseModel):
    """List of top customers."""
    limit: int
    customers: List[TopCustomer]


# ─── Ingestion Schemas ───────────────────────────────────────────────────────

class IngestionStatus(BaseModel):
    """Status of data ingestion process."""
    status: str
    message: str
    customers_ingested: int = 0
    orders_ingested: int = 0
    refunds_ingested: int = 0
    elapsed_seconds: float = 0.0


class IngestionTrigger(BaseModel):
    """Response when ingestion is triggered."""
    status: str
    message: str


# ─── Health Check ────────────────────────────────────────────────────────────

class HealthCheck(BaseModel):
    status: str = "healthy"
    database: str = "connected"
    redis: str = "connected"
