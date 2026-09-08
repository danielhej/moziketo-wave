from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.background_job import JobKind
from app.services import admin_ops


async def enqueue_import(session: AsyncSession, *, limit: int = 0) -> UUID:
    job = await admin_ops.create_job(session, kind=JobKind.IMPORT_CATALOG, payload={"limit": limit})
    await _dispatch(JobKind.IMPORT_CATALOG, str(job.id), limit=limit)
    return job.id


async def enqueue_reindex(session: AsyncSession) -> UUID:
    job = await admin_ops.create_job(session, kind=JobKind.REINDEX_SEARCH, payload={})
    await _dispatch(JobKind.REINDEX_SEARCH, str(job.id))
    return job.id


async def enqueue_webhook_retry(session: AsyncSession) -> UUID:
    job = await admin_ops.create_job(session, kind=JobKind.WEBHOOK_DELIVERY, payload={})
    await _dispatch(JobKind.WEBHOOK_DELIVERY, str(job.id))
    return job.id


async def enqueue_prune_plays(session: AsyncSession) -> UUID:
    job = await admin_ops.create_job(session, kind=JobKind.PRUNE_PLAY_EVENTS, payload={})
    await _dispatch(JobKind.PRUNE_PLAY_EVENTS, str(job.id))
    return job.id


async def enqueue_webhook_deliveries() -> None:
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        await enqueue_webhook_retry(session)


async def _dispatch(kind: str, job_id: str, **kwargs: Any) -> None:
    settings = get_settings()
    if settings.taskiq_inline:
        await _run_inline(kind, UUID(job_id), **kwargs)
        return
    from app.tasks.worker import (
        import_catalog_task,
        prune_plays_task,
        reindex_search_task,
        webhook_delivery_task,
    )

    if kind == JobKind.IMPORT_CATALOG:
        await import_catalog_task.kiq(job_id, kwargs.get("limit", 0))
    elif kind == JobKind.REINDEX_SEARCH:
        await reindex_search_task.kiq(job_id)
    elif kind == JobKind.WEBHOOK_DELIVERY:
        await webhook_delivery_task.kiq(job_id)
    elif kind == JobKind.PRUNE_PLAY_EVENTS:
        await prune_plays_task.kiq(job_id)


async def _run_inline(kind: str, job_id: UUID, **kwargs: Any) -> None:
    from app.tasks.runner import (
        run_import_job,
        run_prune_plays_job,
        run_reindex_job,
        run_webhook_job,
    )

    if kind == JobKind.IMPORT_CATALOG:
        await run_import_job(job_id, limit=int(kwargs.get("limit", 0)))
    elif kind == JobKind.REINDEX_SEARCH:
        await run_reindex_job(job_id)
    elif kind == JobKind.WEBHOOK_DELIVERY:
        await run_webhook_job(job_id)
    elif kind == JobKind.PRUNE_PLAY_EVENTS:
        await run_prune_plays_job(job_id)


async def get_job_response(session: AsyncSession, job_id: UUID) -> dict[str, Any] | None:
    job = await admin_ops.get_job(session, job_id)
    if job is None:
        return None
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "payload": job.payload_json,
        "result": job.result_json,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
