import json
import os
from typing import Any

from app.core.config import get_settings
from app.core.redis import get_redis


async def cache_get(key: str) -> Any | None:
    if os.getenv("DISABLE_CACHE"):
        return None
    try:
        redis = get_redis()
    except RuntimeError:
        return None
    raw = await redis.get(f"wave:{key}")
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    if os.getenv("DISABLE_CACHE"):
        return
    try:
        redis = get_redis()
    except RuntimeError:
        return
    settings = get_settings()
    await redis.set(f"wave:{key}", json.dumps(value), ex=ttl or settings.cache_ttl_seconds)


async def cache_delete(key: str) -> None:
    if os.getenv("DISABLE_CACHE"):
        return
    try:
        redis = get_redis()
    except RuntimeError:
        return
    await redis.delete(f"wave:{key}")


async def cache_delete_pattern(pattern: str) -> None:
    if os.getenv("DISABLE_CACHE"):
        return
    try:
        redis = get_redis()
    except RuntimeError:
        return
    async for key in redis.scan_iter(match=f"wave:{pattern}"):
        await redis.delete(key)
