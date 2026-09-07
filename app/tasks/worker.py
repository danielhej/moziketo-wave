from __future__ import annotations

from uuid import UUID

from app.tasks.broker import broker
from app.tasks.runner import run_import_job, run_reindex_job, run_webhook_job


@broker.task
async def import_catalog_task(job_id: str, limit: int = 0) -> None:
    await run_import_job(UUID(job_id), limit=limit)


@broker.task
async def reindex_search_task(job_id: str) -> None:
    await run_reindex_job(UUID(job_id))


@broker.task
async def webhook_delivery_task(job_id: str) -> None:
    await run_webhook_job(UUID(job_id))
