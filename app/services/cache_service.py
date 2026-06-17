"""
Redis caching service for analytics performance optimization.

Provides get/set operations with TTL-based cache invalidation.
Uses orjson for fast JSON serialization.
"""

import logging
from typing import Optional, Any

import orjson
import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Redis connection pool
_redis_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def close_redis():
    """Close Redis connection."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


def _serialize(value: Any) -> str:
    """Serialize a Python object to a JSON string."""
    return orjson.dumps(value, default=str).decode()


def _deserialize(value: str) -> Any:
    """Deserialize a JSON string to a Python object."""
    return orjson.loads(value)


async def cache_get(key: str) -> Optional[Any]:
    """
    Get cached value by key.

    Returns deserialized Python object or None if not cached.
    """
    try:
        r = await get_redis()
        value = await r.get(key)
        if value is not None:
            return _deserialize(value)
        return None
    except Exception as e:
        logger.warning(f"Redis cache GET error for key '{key}': {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """
    Set cached value with TTL.

    Args:
        key: Cache key
        value: Python object to cache (must be JSON-serializable)
        ttl: Time-to-live in seconds (default: from settings)

    Returns:
        True if cached successfully
    """
    ttl = ttl or settings.CACHE_TTL_SECONDS
    try:
        r = await get_redis()
        await r.set(key, _serialize(value), ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"Redis cache SET error for key '{key}': {e}")
        return False


async def cache_delete(key: str) -> bool:
    """Delete a cached key."""
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis cache DELETE error for key '{key}': {e}")
        return False


async def cache_clear_analytics() -> bool:
    """Clear all analytics-related cache keys."""
    try:
        r = await get_redis()
        keys = []
        async for key in r.scan_iter(match="analytics:*"):
            keys.append(key)
        if keys:
            await r.delete(*keys)
        logger.info(f"Cleared {len(keys)} analytics cache keys")
        return True
    except Exception as e:
        logger.warning(f"Redis cache CLEAR error: {e}")
        return False
