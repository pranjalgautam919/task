"""
Ingestion API endpoints.

Provides endpoints to trigger data ingestion from mock APIs
and check ingestion status.
"""

import asyncio

from fastapi import APIRouter

from app.schemas import IngestionStatus, IngestionTrigger
from app.services.ingestion_service import run_ingestion, get_ingestion_status

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])

# Prevent concurrent start requests from spawning duplicate ingestion tasks
_start_lock = asyncio.Lock()


@router.post(
    "/start",
    response_model=IngestionTrigger,
    summary="Start data ingestion",
    description=(
        "Triggers the ingestion pipeline that pulls data from mock APIs "
        "and stores it in PostgreSQL. Runs as a background task."
    ),
)
async def start_ingestion():
    """
    Start the data ingestion pipeline.

    This endpoint triggers a background task that:
    1. Pulls all customers, orders, and refunds from mock APIs
    2. Handles pagination automatically
    3. Batch inserts data into PostgreSQL
    4. Refreshes materialized views
    5. Clears analytics cache

    Check status via GET /api/ingest/status.
    """
    async with _start_lock:
        current_status = await get_ingestion_status()
        if current_status["status"] == "running":
            return IngestionTrigger(
                status="already_running",
                message="Ingestion is already in progress. Check /api/ingest/status for updates.",
            )

        asyncio.create_task(run_ingestion())

    return IngestionTrigger(
        status="started",
        message="Ingestion pipeline started. Check /api/ingest/status for progress.",
    )


@router.get(
    "/status",
    response_model=IngestionStatus,
    summary="Get ingestion status",
    description="Returns the current status of the data ingestion pipeline.",
)
async def ingestion_status():
    """
    Get current ingestion status.

    Returns:
    - **status**: idle, running, completed, or failed
    - **message**: Human-readable status message
    - **customers_ingested**: Number of customers inserted
    - **orders_ingested**: Number of orders inserted
    - **refunds_ingested**: Number of refunds inserted
    - **elapsed_seconds**: Time elapsed since ingestion start
    """
    return await get_ingestion_status()
