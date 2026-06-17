"""
Analytics API endpoints.

All endpoints are optimized for < 2 second response times through:
- Materialized views for pre-aggregated data
- Redis caching (60s TTL)
- Proper database indexes
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    AnalyticsSummary,
    RepeatCustomerRevenue,
    RevenueTrends,
    TopCustomersResponse,
)
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Get analytics summary",
    description=(
        "Returns total orders, total revenue, total refunds, "
        "total refund amount, net revenue, and average order value."
    ),
)
async def get_summary(db: AsyncSession = Depends(get_db)):
    """
    Get overall analytics summary.

    Metrics included:
    - **total_orders**: Count of all non-cancelled orders
    - **total_revenue**: Sum of all non-cancelled order amounts
    - **total_refunds**: Count of completed refunds
    - **total_refund_amount**: Sum of completed refund amounts
    - **net_revenue**: total_revenue - total_refund_amount
    - **avg_order_value**: total_revenue / total_orders
    """
    return await analytics_service.get_analytics_summary(db)


@router.get(
    "/repeat-customers/revenue",
    response_model=RepeatCustomerRevenue,
    summary="Get repeat customer revenue",
    description="Returns revenue and count from customers who placed more than one order.",
)
async def get_repeat_customer_revenue(db: AsyncSession = Depends(get_db)):
    """
    Get revenue from repeat customers.

    Repeat customers = customers with more than 1 order.
    Returns count, total revenue, and percentage of total revenue.
    """
    return await analytics_service.get_repeat_customer_revenue(db)


@router.get(
    "/revenue-trends",
    response_model=RevenueTrends,
    summary="Get revenue trends",
    description="Returns revenue trends aggregated by day or month.",
)
async def get_revenue_trends(
    period: str = Query(
        "daily",
        pattern="^(daily|monthly)$",
        description="Aggregation period: 'daily' or 'monthly'",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get revenue trends over time.

    - **daily**: Revenue per day
    - **monthly**: Revenue per month
    """
    return await analytics_service.get_revenue_trends(db, period)


@router.get(
    "/top-customers",
    response_model=TopCustomersResponse,
    summary="Get top customers by spend",
    description="Returns top N customers ranked by total spend.",
)
async def get_top_customers(
    limit: int = Query(
        10, ge=1, le=100, description="Number of top customers to return"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top customers by total spend.

    Returns customer details including name, email, total orders, and total spend.
    """
    return await analytics_service.get_top_customers(db, limit)
