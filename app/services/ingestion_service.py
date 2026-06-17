"""
Ingestion service — pulls data from mock APIs and stores in PostgreSQL.

Features:
- Async HTTP client with concurrent pagination fetching
- Batch inserts for efficient data loading
- Progress tracking (Redis-backed for multi-worker support)
- Materialized view refresh after ingestion
- Idempotent (uses ON CONFLICT DO NOTHING)
"""

import asyncio
import logging
import time
from typing import Dict, List

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import async_session_factory, refresh_materialized_views
from app.services.cache_service import cache_clear_analytics, cache_get, cache_set
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

INGESTION_STATUS_KEY = "ingestion:status"
INGESTION_STATUS_TTL = 3600  # 1 hour

# In-memory fallback when Redis is unavailable
_ingestion_status: Dict = {
    "status": "idle",
    "message": "No ingestion running",
    "customers_ingested": 0,
    "orders_ingested": 0,
    "refunds_ingested": 0,
    "elapsed_seconds": 0.0,
}
_ingestion_lock = asyncio.Lock()


async def _persist_status(status: Dict) -> None:
    """Persist ingestion status to Redis and in-memory fallback."""
    global _ingestion_status
    _ingestion_status = status.copy()
    await cache_set(INGESTION_STATUS_KEY, status, ttl=INGESTION_STATUS_TTL)


async def get_ingestion_status() -> Dict:
    """Get current ingestion status (Redis-backed with in-memory fallback)."""
    cached = await cache_get(INGESTION_STATUS_KEY)
    if cached:
        return cached
    return _ingestion_status.copy()


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    page: int,
    page_size: int,
) -> dict:
    """Fetch a single page from a mock API endpoint."""
    response = await client.get(
        url,
        params={"page": page, "page_size": page_size},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


async def _fetch_all_pages(
    client: httpx.AsyncClient,
    endpoint: str,
    page_size: int = 1000,
    concurrency: int = 10,
) -> List[dict]:
    """
    Fetch all pages from a mock API endpoint concurrently.

    Uses a semaphore to limit concurrent requests.
    """
    url = f"{settings.MOCK_API_BASE_URL.rstrip('/')}{endpoint}"

    # First, get page 1 to determine total pages
    first_page = await _fetch_page(client, url, 1, page_size)
    total_pages = first_page.get("total_pages", 0)
    all_data = list(first_page.get("data", []))

    if total_pages <= 1:
        return all_data

    # Fetch remaining pages concurrently with semaphore
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(page_num: int) -> List[dict]:
        async with semaphore:
            result = await _fetch_page(client, url, page_num, page_size)
            return result.get("data", [])

    tasks = [
        fetch_with_semaphore(page_num)
        for page_num in range(2, total_pages + 1)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Error fetching page: {result}")
            raise result
        all_data.extend(result)

    return all_data


async def _batch_insert_customers(
    session: AsyncSession, customers: List[dict]
) -> int:
    """Batch insert customers using raw SQL for performance."""
    if not customers:
        return 0

    inserted = 0
    batch_size = settings.INGESTION_BATCH_SIZE

    for i in range(0, len(customers), batch_size):
        batch = customers[i : i + batch_size]
        values_parts = []
        params = {}

        for j, c in enumerate(batch):
            prefix = f"c{i + j}"
            values_parts.append(
                f"(:{prefix}_id, :{prefix}_name, :{prefix}_email, "
                f":{prefix}_phone, :{prefix}_address, :{prefix}_city, "
                f":{prefix}_state, :{prefix}_country, :{prefix}_zip_code, "
                f"CAST(:{prefix}_created_at AS TIMESTAMP))"
            )
            params[f"{prefix}_id"] = c["id"]
            params[f"{prefix}_name"] = c["name"]
            params[f"{prefix}_email"] = c["email"]
            params[f"{prefix}_phone"] = c.get("phone")
            params[f"{prefix}_address"] = c.get("address")
            params[f"{prefix}_city"] = c.get("city")
            params[f"{prefix}_state"] = c.get("state")
            params[f"{prefix}_country"] = c.get("country")
            params[f"{prefix}_zip_code"] = c.get("zip_code")
            params[f"{prefix}_created_at"] = c["created_at"]

        sql = f"""
            INSERT INTO customers (id, name, email, phone, address, city, state, country, zip_code, created_at)
            VALUES {', '.join(values_parts)}
            ON CONFLICT (id) DO NOTHING;
        """
        result = await session.execute(text(sql), params)
        await session.commit()
        if result.rowcount is not None and result.rowcount >= 0:
            inserted += result.rowcount

    return inserted


async def _batch_insert_orders(
    session: AsyncSession, orders: List[dict]
) -> int:
    """Batch insert orders using raw SQL for performance."""
    if not orders:
        return 0

    inserted = 0
    batch_size = settings.INGESTION_BATCH_SIZE

    for i in range(0, len(orders), batch_size):
        batch = orders[i : i + batch_size]
        values_parts = []
        params = {}

        for j, o in enumerate(batch):
            prefix = f"o{i + j}"
            values_parts.append(
                f"(:{prefix}_id, :{prefix}_customer_id, "
                f":{prefix}_total_amount, :{prefix}_status, "
                f"CAST(:{prefix}_order_date AS TIMESTAMP), "
                f"CAST(:{prefix}_created_at AS TIMESTAMP))"
            )
            params[f"{prefix}_id"] = o["id"]
            params[f"{prefix}_customer_id"] = o["customer_id"]
            params[f"{prefix}_total_amount"] = o["total_amount"]
            params[f"{prefix}_status"] = o["status"]
            params[f"{prefix}_order_date"] = o["order_date"]
            params[f"{prefix}_created_at"] = o.get(
                "created_at", o["order_date"]
            )

        sql = f"""
            INSERT INTO orders (id, customer_id, total_amount, status, order_date, created_at)
            VALUES {', '.join(values_parts)}
            ON CONFLICT (id) DO NOTHING;
        """
        result = await session.execute(text(sql), params)
        await session.commit()
        if result.rowcount is not None and result.rowcount >= 0:
            inserted += result.rowcount

    return inserted


async def _batch_insert_refunds(
    session: AsyncSession, refunds: List[dict]
) -> int:
    """Batch insert refunds using raw SQL for performance."""
    if not refunds:
        return 0

    inserted = 0
    batch_size = settings.INGESTION_BATCH_SIZE

    for i in range(0, len(refunds), batch_size):
        batch = refunds[i : i + batch_size]
        values_parts = []
        params = {}

        for j, r in enumerate(batch):
            prefix = f"r{i + j}"
            values_parts.append(
                f"(:{prefix}_id, :{prefix}_order_id, "
                f":{prefix}_refund_amount, :{prefix}_reason, "
                f":{prefix}_status, CAST(:{prefix}_refund_date AS TIMESTAMP), "
                f"CAST(:{prefix}_created_at AS TIMESTAMP))"
            )
            params[f"{prefix}_id"] = r["id"]
            params[f"{prefix}_order_id"] = r["order_id"]
            params[f"{prefix}_refund_amount"] = r["refund_amount"]
            params[f"{prefix}_reason"] = r.get("reason")
            params[f"{prefix}_status"] = r["status"]
            params[f"{prefix}_refund_date"] = r["refund_date"]
            params[f"{prefix}_created_at"] = r.get(
                "created_at", r["refund_date"]
            )

        sql = f"""
            INSERT INTO refunds (id, order_id, refund_amount, reason, status, refund_date, created_at)
            VALUES {', '.join(values_parts)}
            ON CONFLICT (id) DO NOTHING;
        """
        result = await session.execute(text(sql), params)
        await session.commit()
        if result.rowcount is not None and result.rowcount >= 0:
            inserted += result.rowcount

    return inserted


async def _update_status(updates: Dict) -> None:
    """Merge updates into current status and persist."""
    current = await get_ingestion_status()
    current.update(updates)
    await _persist_status(current)


async def run_ingestion():
    """
    Run the full ingestion pipeline.

    1. Pull data from mock APIs (with pagination)
    2. Batch insert into PostgreSQL
    3. Refresh materialized views
    4. Clear analytics cache
    """
    async with _ingestion_lock:
        current = await get_ingestion_status()
        if current["status"] == "running":
            logger.warning("Ingestion already running, skipping duplicate request")
            return

        start_time = time.time()
        status = {
            "status": "running",
            "message": "Ingestion started",
            "customers_ingested": 0,
            "orders_ingested": 0,
            "refunds_ingested": 0,
            "elapsed_seconds": 0.0,
        }
        await _persist_status(status)

        customers_count = 0
        orders_count = 0
        refunds_count = 0

        try:
            async with httpx.AsyncClient() as client:
                await _update_status({"message": "Fetching customers from mock API..."})
                logger.info("Fetching customers...")
                customers = await _fetch_all_pages(
                    client, "/api/mock/customers",
                    page_size=settings.DEFAULT_PAGE_SIZE,
                    concurrency=settings.INGESTION_CONCURRENCY,
                )
                logger.info(f"Fetched {len(customers)} customers")

                await _update_status({"message": "Fetching orders from mock API..."})
                logger.info("Fetching orders...")
                orders = await _fetch_all_pages(
                    client, "/api/mock/orders",
                    page_size=settings.DEFAULT_PAGE_SIZE,
                    concurrency=settings.INGESTION_CONCURRENCY,
                )
                logger.info(f"Fetched {len(orders)} orders")

                await _update_status({"message": "Fetching refunds from mock API..."})
                logger.info("Fetching refunds...")
                refunds = await _fetch_all_pages(
                    client, "/api/mock/refunds",
                    page_size=settings.DEFAULT_PAGE_SIZE,
                    concurrency=settings.INGESTION_CONCURRENCY,
                )
                logger.info(f"Fetched {len(refunds)} refunds")

            async with async_session_factory() as session:
                await _update_status({"message": "Inserting customers into database..."})
                logger.info("Inserting customers...")
                customers_count = await _batch_insert_customers(session, customers)
                await _update_status({"customers_ingested": customers_count})

                await _update_status({"message": "Inserting orders into database..."})
                logger.info("Inserting orders...")
                orders_count = await _batch_insert_orders(session, orders)
                await _update_status({"orders_ingested": orders_count})

                await _update_status({"message": "Inserting refunds into database..."})
                logger.info("Inserting refunds...")
                refunds_count = await _batch_insert_refunds(session, refunds)
                await _update_status({"refunds_ingested": refunds_count})

            await _update_status({"message": "Refreshing materialized views..."})
            logger.info("Refreshing materialized views...")
            await refresh_materialized_views()

            await _update_status({"message": "Clearing analytics cache..."})
            await cache_clear_analytics()

            elapsed = time.time() - start_time
            await _persist_status({
                "status": "completed",
                "message": f"Ingestion completed in {elapsed:.1f}s",
                "customers_ingested": customers_count,
                "orders_ingested": orders_count,
                "refunds_ingested": refunds_count,
                "elapsed_seconds": round(elapsed, 2),
            })
            logger.info(
                f"Ingestion completed: {customers_count} customers, "
                f"{orders_count} orders, {refunds_count} refunds "
                f"in {elapsed:.1f}s"
            )

        except Exception as e:
            elapsed = time.time() - start_time
            await _persist_status({
                "status": "failed",
                "message": f"Ingestion failed: {str(e)}",
                "customers_ingested": customers_count,
                "orders_ingested": orders_count,
                "refunds_ingested": refunds_count,
                "elapsed_seconds": round(elapsed, 2),
            })
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            raise
