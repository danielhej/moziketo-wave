from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Album, Artist, BackgroundJob, JobKind, JobStatus, Track, User
from app.schemas.admin_ops import AdminCatalogSummary, AdminUsersResponse, AdminUserSummary
from app.services.media import published_album_filter, published_track_filter


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked = "*" * len(local)
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


async def catalog_summary(session: AsyncSession) -> AdminCatalogSummary:
    tracks = await session.scalar(select(func.count()).select_from(Track)) or 0
    published = (
        await session.scalar(
            select(func.count()).select_from(Track).where(published_track_filter())
        )
        or 0
    )
    artists = await session.scalar(select(func.count()).select_from(Artist)) or 0
    albums = await session.scalar(select(func.count()).select_from(Album)) or 0
    albums_pub = (
        await session.scalar(
            select(func.count()).select_from(Album).where(published_album_filter())
        )
        or 0
    )
    users = await session.scalar(select(func.count()).select_from(User)) or 0
    return AdminCatalogSummary(
        tracks_total=tracks,
        tracks_published=published,
        artists_total=artists,
        albums_total=albums,
        albums_published=albums_pub,
        users_total=users,
    )


async def list_users(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> AdminUsersResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    rows = await session.scalars(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [
        AdminUserSummary(
            id=str(u.id),
            email=_mask_email(u.email),
            display_name=u.display_name,
            is_active=u.is_active,
            email_verified=u.email_verified_at is not None,
            deleted=u.deleted_at is not None,
            created_at=u.created_at,
        )
        for u in rows
    ]
    return AdminUsersResponse(items=items, total=total, page=page, page_size=page_size)


async def set_user_active(session: AsyncSession, user_id: UUID, *, active: bool) -> None:
    from fastapi import HTTPException, status

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = active
    await session.commit()


async def latest_import_job(session: AsyncSession) -> BackgroundJob | None:
    return await session.scalar(
        select(BackgroundJob)
        .where(BackgroundJob.kind == JobKind.IMPORT_CATALOG)
        .order_by(BackgroundJob.created_at.desc())
        .limit(1)
    )


async def create_job(
    session: AsyncSession, *, kind: str, payload: dict[str, Any] | None = None
) -> BackgroundJob:
    job = BackgroundJob(kind=kind, status=JobStatus.QUEUED, payload_json=payload)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def mark_job_running(session: AsyncSession, job_id: UUID) -> BackgroundJob:
    job = await session.get(BackgroundJob, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    job.status = JobStatus.RUNNING
    await session.commit()
    await session.refresh(job)
    return job


async def mark_job_completed(
    session: AsyncSession, job_id: UUID, result: dict[str, Any]
) -> None:
    job = await session.get(BackgroundJob, job_id)
    if job is None:
        return
    job.status = JobStatus.COMPLETED
    job.result_json = result
    job.finished_at = datetime.now(UTC)
    await session.commit()


async def mark_job_failed(session: AsyncSession, job_id: UUID, error: str) -> None:
    job = await session.get(BackgroundJob, job_id)
    if job is None:
        return
    job.status = JobStatus.FAILED
    job.error = error
    job.finished_at = datetime.now(UTC)
    await session.commit()


async def get_job(session: AsyncSession, job_id: UUID) -> BackgroundJob | None:
    return await session.get(BackgroundJob, job_id)


async def build_track_doc(session: AsyncSession, track: Track) -> dict[str, Any]:
    await session.refresh(track, ["artist", "tags"])
    return {
        "id": str(track.id),
        "slug": track.slug,
        "title": track.title,
        "artist_name": track.artist.name if track.artist else "",
        "duration_seconds": track.duration_seconds,
        "cover_url": track.cover_url,
        "stream_count": track.stream_count,
        "published": track.published_at is not None,
    }


async def reindex_all(session: AsyncSession) -> dict[str, int]:
    from app.services.search_meili import upsert_documents

    tracks = await session.scalars(
        select(Track).options(selectinload(Track.artist)).where(published_track_filter())
    )
    track_docs = [await build_track_doc(session, t) for t in tracks]
    await upsert_documents("tracks", track_docs)

    artists = await session.scalars(select(Artist))
    artist_docs = [
        {
            "id": str(a.id),
            "slug": a.slug,
            "name": a.name,
            "name_en": a.name_en,
            "cover_url": a.cover_url,
            "track_count": 0,
        }
        for a in artists
    ]
    await upsert_documents("artists", artist_docs)

    albums = await session.scalars(
        select(Album).options(selectinload(Album.artist)).where(published_album_filter())
    )
    album_docs = [
        {
            "id": str(a.id),
            "slug": a.slug,
            "title": a.title,
            "artist_name": a.artist.name if a.artist else "",
            "published": True,
        }
        for a in albums
    ]
    await upsert_documents("albums", album_docs)
    return {
        "tracks": len(track_docs),
        "artists": len(artist_docs),
        "albums": len(album_docs),
    }
