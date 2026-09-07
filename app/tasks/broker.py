from __future__ import annotations

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.core.config import get_settings

settings = get_settings()
result_backend = RedisAsyncResultBackend(settings.redis_url)
broker = ListQueueBroker(settings.redis_url, queue_name="wave_tasks").with_result_backend(
    result_backend
)
