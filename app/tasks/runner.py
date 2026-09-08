from __future__ import annotations

from uuid import UUID

from app.db.session import SessionLocal
from app.models.background_job import JobKind
from app.models.webhook import WebhookEvent
from app.services import admin_ops, import_wp
from app.services.history import prune_all_users
from app.services.webhooks import deliver_pending, emit_event


async def run_import_job(job_id: UUID, *, limit: int = 0) -> None:
    async with SessionLocal() as session:
        await admin_ops.mark_job_running(session, job_id)
        try:
            result = await import_wp.run_import(session, limit=limit)
            payload = result.model_dump()
            await admin_ops.mark_job_completed(session, job_id, payload)
            await emit_event(
                session,
                WebhookEvent.IMPORT_COMPLETED,
                {"job_id": str(job_id), **payload},
            )
        except Exception as exc:
            await admin_ops.mark_job_failed(session, job_id, str(exc))
            raise

    async with SessionLocal() as session:
        reindex_job = await admin_ops.create_job(session, kind=JobKind.REINDEX_SEARCH, payload={})
    await run_reindex_job(reindex_job.id)


async def run_reindex_job(job_id: UUID) -> None:
    async with SessionLocal() as session:
        await admin_ops.mark_job_running(session, job_id)
        try:
            counts = await admin_ops.reindex_all(session)
            await admin_ops.mark_job_completed(session, job_id, counts)
        except Exception as exc:
            await admin_ops.mark_job_failed(session, job_id, str(exc))
            raise


async def run_webhook_job(job_id: UUID) -> None:
    async with SessionLocal() as session:
        await admin_ops.mark_job_running(session, job_id)
        try:
            delivered = await deliver_pending(session)
            await admin_ops.mark_job_completed(session, job_id, {"delivered": delivered})
        except Exception as exc:
            await admin_ops.mark_job_failed(session, job_id, str(exc))
            raise


async def run_prune_plays_job(job_id: UUID) -> None:
    async with SessionLocal() as session:
        await admin_ops.mark_job_running(session, job_id)
        try:
            result = await prune_all_users(session)
            await admin_ops.mark_job_completed(session, job_id, result)
        except Exception as exc:
            await admin_ops.mark_job_failed(session, job_id, str(exc))
            raise
