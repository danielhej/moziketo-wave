from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request, status

from app.core.redis import connect_redis, get_redis


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _redis_key(scope: str, key: str) -> str:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"ratelimit:{scope}:{digest}"


async def check_rate_limit(
    scope: str,
    key: str,
    *,
    limit: int,
    window_seconds: int,
    enabled: bool = True,
) -> None:
    if not enabled:
        return

    await connect_redis()
    redis = get_redis()
    redis_key = _redis_key(scope, key)
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)

    if count > limit:
        ttl = await redis.ttl(redis_key)
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(retry_after)},
        )
