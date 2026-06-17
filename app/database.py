"""Async SQLAlchemy database engine and session management."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and materialized views."""
    # Import models so they are registered with Base.metadata before create_all
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create materialized views for analytics performance
    async with async_session_factory() as session:
        # Materialized view: daily revenue
        await session.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_revenue AS
            SELECT
                DATE(order_date) AS order_day,
                COUNT(*) AS order_count,
                COALESCE(SUM(total_amount), 0) AS daily_revenue
            FROM orders
            WHERE status != 'cancelled'
            GROUP BY DATE(order_date)
            ORDER BY order_day;
        """))

        # Materialized view: customer spend
        await session.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_spend AS
            SELECT
                o.customer_id,
                c.name AS customer_name,
                c.email AS customer_email,
                COUNT(o.id) AS total_orders,
                COALESCE(SUM(o.total_amount), 0) AS total_spend
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE o.status != 'cancelled'
            GROUP BY o.customer_id, c.name, c.email;
        """))

        # Materialized view: analytics summary (single row with all key metrics)
        await session.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_analytics_summary AS
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
                (
                    (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled')
                    /
                    NULLIF((SELECT COUNT(*) FROM orders WHERE status != 'cancelled'), 0)
                ) AS avg_order_value;
        """))

        # Create indexes on materialized views (required for CONCURRENTLY refresh)
        await session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_revenue_day
            ON mv_daily_revenue (order_day);
        """))
        await session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_customer_spend_id
            ON mv_customer_spend (customer_id);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mv_customer_spend_total
            ON mv_customer_spend (total_spend DESC);
        """))

        await session.commit()


async def _refresh_mv(session: AsyncSession, view_name: str, concurrently: bool = True):
    """Refresh a materialized view with fallback to non-concurrent refresh."""
    mode = "CONCURRENTLY" if concurrently else ""
    try:
        await session.execute(text(
            f"REFRESH MATERIALIZED VIEW {mode} {view_name};"
        ))
    except Exception as exc:
        if concurrently:
            logger.warning(
                "Concurrent refresh failed for %s (%s), retrying without CONCURRENTLY",
                view_name,
                exc,
            )
            await session.execute(text(
                f"REFRESH MATERIALIZED VIEW {view_name};"
            ))
        else:
            raise


async def refresh_materialized_views():
    """Refresh all materialized views. Called after data ingestion."""
    async with async_session_factory() as session:
        await _refresh_mv(session, "mv_daily_revenue", concurrently=True)
        await _refresh_mv(session, "mv_customer_spend", concurrently=True)
        # Single-row summary view has no unique index — non-concurrent only
        await _refresh_mv(session, "mv_analytics_summary", concurrently=False)
        await session.commit()
