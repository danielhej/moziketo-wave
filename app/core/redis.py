import redis.asyncio as redis

_redis: redis.Redis | None = None


async def connect_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.ping()
            return
        except Exception:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None

    from app.core.config import get_settings

    settings = get_settings()
    _redis = redis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()


async def disconnect_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None


async def check_redis() -> bool:
    if _redis is None:
        try:
            await connect_redis()
        except Exception:
            return False
    try:
        await _redis.ping()
        return True
    except Exception:
        return False


def get_redis() -> redis.Redis:
    if _redis is None:
        raise RuntimeError("Redis is not connected")
    return _redis
