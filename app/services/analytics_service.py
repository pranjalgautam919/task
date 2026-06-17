"""
Analytics service — executes optimized queries against PostgreSQL.

Uses materialized views for pre-aggregated data and Redis caching
to ensure all analytics endpoints respond in < 2 seconds.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.cache_service import cache_get, cache_set

logger = logging.getLogger(__name__)

# Cache key constants
CACHE_SUMMARY = "analytics:summary"
CACHE_REPEAT_REVENUE = "analytics:repeat_customer_revenue"
CACHE_TRENDS_DAILY = "analytics:revenue_trends:daily"
CACHE_TRENDS_MONTHLY = "analytics:revenue_trends:monthly"
CACHE_TOP_CUSTOMERS = "analytics:top_customers:{limit}"


def _empty_summary() -> dict:
    return {
        "total_orders": 0,
        "total_revenue": 0.0,
        "total_refunds": 0,
        "total_refund_amount": 0.0,
        "net_revenue": 0.0,
        "avg_order_value": 0.0,
    }


async def get_analytics_summary(db: AsyncSession) -> dict:
    """
    Get overall analytics summary.

    Returns total_orders, total_revenue, total_refunds,
    total_refund_amount, net_revenue, avg_order_value.

    Uses materialized view mv_analytics_summary for instant reads.
    """
    cached = await cache_get(CACHE_SUMMARY)
    if cached:
        return cached

    result = await db.execute(text("""
        SELECT
            total_orders,
            total_revenue,
            total_refunds,
            total_refund_amount,
            net_revenue,
            avg_order_value
        FROM mv_analytics_summary
        LIMIT 1;
    """))

    row = result.mappings().first()
    if row is None:
        result = await db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM orders WHERE status != 'cancelled') AS total_orders,
                (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled') AS total_revenue,
                (SELECT COUNT(*) FROM refunds WHERE status = 'completed') AS total_refunds,
                (SELECT COALESCE(SUM(refund_amount), 0) FROM refunds WHERE status = 'completed') AS total_refund_amount,
                (
                    (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled')
                    -
                    (SELECT COALESCE(SUM(refund_amount), 0) FROM refunds WHERE status = 'completed')
                ) AS net_revenue,
                CASE
                    WHEN (SELECT COUNT(*) FROM orders WHERE status != 'cancelled') > 0
                    THEN (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled')
                         / (SELECT COUNT(*) FROM orders WHERE status != 'cancelled')
                    ELSE 0
                END AS avg_order_value;
        """))
        row = result.mappings().first()

    if row is None:
        data = _empty_summary()
    else:
        data = {
            "total_orders": int(row["total_orders"] or 0),
            "total_revenue": round(float(row["total_revenue"] or 0), 2),
            "total_refunds": int(row["total_refunds"] or 0),
            "total_refund_amount": round(float(row["total_refund_amount"] or 0), 2),
            "net_revenue": round(float(row["net_revenue"] or 0), 2),
            "avg_order_value": round(float(row["avg_order_value"] or 0), 2),
        }

    await cache_set(CACHE_SUMMARY, data)
    return data


async def get_repeat_customer_revenue(db: AsyncSession) -> dict:
    """
    Get revenue from repeat customers (customers with > 1 order).

    Uses mv_customer_spend materialized view.
    """
    cached = await cache_get(CACHE_REPEAT_REVENUE)
    if cached:
        return cached

    result = await db.execute(text("""
        SELECT
            COUNT(*) AS repeat_customer_count,
            COALESCE(SUM(total_spend), 0) AS repeat_customer_revenue
        FROM mv_customer_spend
        WHERE total_orders > 1;
    """))
    row = result.mappings().first()

    total_result = await db.execute(text("""
        SELECT COALESCE(SUM(total_spend), 0) AS total_revenue
        FROM mv_customer_spend;
    """))
    total_row = total_result.mappings().first()
    total_revenue = float(total_row["total_revenue"] or 0) if total_row else 0.0

    repeat_revenue = float(row["repeat_customer_revenue"] or 0) if row else 0.0
    repeat_count = int(row["repeat_customer_count"] or 0) if row else 0
    percentage = (
        round((repeat_revenue / total_revenue) * 100, 2)
        if total_revenue > 0 else 0.0
    )

    data = {
        "repeat_customer_count": repeat_count,
        "repeat_customer_revenue": round(repeat_revenue, 2),
        "repeat_customer_percentage": percentage,
    }

    await cache_set(CACHE_REPEAT_REVENUE, data)
    return data


async def get_revenue_trends(
    db: AsyncSession, period: str = "daily"
) -> dict:
    """
    Get revenue trends over time.

    Args:
        period: 'daily' or 'monthly'

    Uses mv_daily_revenue materialized view.
    """
    cache_key = (
        CACHE_TRENDS_DAILY if period == "daily" else CACHE_TRENDS_MONTHLY
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    if period == "monthly":
        result = await db.execute(text("""
            SELECT
                TO_CHAR(order_day, 'YYYY-MM') AS period,
                SUM(order_count)::int AS order_count,
                COALESCE(SUM(daily_revenue), 0) AS revenue
            FROM mv_daily_revenue
            GROUP BY TO_CHAR(order_day, 'YYYY-MM')
            ORDER BY period;
        """))
    else:
        result = await db.execute(text("""
            SELECT
                TO_CHAR(order_day, 'YYYY-MM-DD') AS period,
                order_count,
                daily_revenue AS revenue
            FROM mv_daily_revenue
            ORDER BY order_day;
        """))

    rows = result.mappings().all()
    trend_data = [
        {
            "period": row["period"],
            "order_count": int(row["order_count"] or 0),
            "revenue": round(float(row["revenue"] or 0), 2),
        }
        for row in rows
    ]

    data = {
        "period_type": period,
        "data": trend_data,
    }

    await cache_set(cache_key, data)
    return data


async def get_top_customers(
    db: AsyncSession, limit: int = 10
) -> dict:
    """
    Get top customers by total spend.

    Uses mv_customer_spend materialized view with index on total_spend.
    """
    cache_key = CACHE_TOP_CUSTOMERS.format(limit=limit)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await db.execute(text("""
        SELECT
            customer_id,
            customer_name,
            customer_email,
            total_orders,
            total_spend
        FROM mv_customer_spend
        ORDER BY total_spend DESC
        LIMIT :limit;
    """), {"limit": limit})

    rows = result.mappings().all()
    customers = [
        {
            "customer_id": row["customer_id"],
            "customer_name": row["customer_name"],
            "customer_email": row["customer_email"],
            "total_orders": int(row["total_orders"] or 0),
            "total_spend": round(float(row["total_spend"] or 0), 2),
        }
        for row in rows
    ]

    data = {
        "limit": limit,
        "customers": customers,
    }

    await cache_set(cache_key, data)
    return data
