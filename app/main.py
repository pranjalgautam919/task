"""
FastAPI application entry point.

Configures the app with lifespan management, routers, middleware, and OpenAPI docs.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, engine
import app.models  # noqa: F401 — register ORM models with SQLAlchemy metadata
from app.services.cache_service import close_redis, get_redis
from app.routers import mock_api, ingestion, analytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # ─── Startup ─────────────────────────────────────────────────────
    logger.info("Starting up...")

    # Initialize database tables and materialized views
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

    # Verify Redis connection
    try:
        r = await get_redis()
        await r.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.warning(f"Redis not available: {e}. Caching will be disabled.")

    logger.info("Application started successfully")

    yield

    # ─── Shutdown ────────────────────────────────────────────────────
    logger.info("Shutting down...")
    await close_redis()
    await engine.dispose()
    logger.info("Shutdown complete")


# ─── Create FastAPI App ──────────────────────────────────────────────────────

app = FastAPI(
    title="Analytics Backend Service",
    description=(
        "High-performance backend service for e-commerce analytics.\n\n"
        "## Features\n"
        "- **Data Generation**: 100K customers, 1M orders, 200K refunds\n"
        "- **Mock APIs**: Paginated data access endpoints\n"
        "- **Ingestion Service**: Async bulk data ingestion\n"
        "- **Analytics APIs**: Real-time analytics with < 2s response times\n\n"
        "## Optimization\n"
        "- PostgreSQL materialized views for pre-aggregated data\n"
        "- Redis caching with TTL-based invalidation\n"
        "- Strategic database indexes\n"
        "- Async I/O throughout\n"
        "- Connection pooling\n"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS Middleware ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Register Routers ───────────────────────────────────────────────────────

app.include_router(mock_api.router)
app.include_router(ingestion.router)
app.include_router(analytics.router)


# ─── Health Check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    health = {"status": "healthy", "database": "unknown", "redis": "unknown"}

    # Check database
    try:
        from sqlalchemy import text
        from app.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Redis
    try:
        r = await get_redis()
        await r.ping()
        health["redis"] = "connected"
    except Exception as e:
        health["redis"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Analytics Backend Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "mock_apis": {
                "customers": "/api/mock/customers",
                "orders": "/api/mock/orders",
                "refunds": "/api/mock/refunds",
            },
            "ingestion": {
                "start": "POST /api/ingest/start",
                "status": "GET /api/ingest/status",
            },
            "analytics": {
                "summary": "/api/analytics/summary",
                "repeat_customers": "/api/analytics/repeat-customers/revenue",
                "revenue_trends": "/api/analytics/revenue-trends",
                "top_customers": "/api/analytics/top-customers",
            },
        },
    }
