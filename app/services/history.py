from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import PlayEvent, Track, User
from app.schemas.catalog import TrackListResponse, TrackSummary
from app.services.catalog import _track_summary
from app.services.media import published_track_filter

MAX_PLAY_EVENTS_PER_USER = 500


async def record_play(session: AsyncSession, user: User, track_slug: str) -> None:
    track = await session.scalar(
        select(Track)
        .options(selectinload(Track.artist))
        .where(Track.slug == track_slug, published_track_filter())
    )
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    session.add(PlayEvent(user_id=user.id, track_id=track.id))
    await session.commit()
    await _prune_user_events(session, user.id)


async def _prune_user_events(session: AsyncSession, user_id: UUID) -> None:
    total = await session.scalar(
        select(func.count()).select_from(PlayEvent).where(PlayEvent.user_id == user_id)
    )
    if not total or total <= MAX_PLAY_EVENTS_PER_USER:
        return

    excess = total - MAX_PLAY_EVENTS_PER_USER
    oldest_ids = (
        select(PlayEvent.id)
        .where(PlayEvent.user_id == user_id)
        .order_by(PlayEvent.played_at.asc())
        .limit(excess)
    )
    await session.execute(delete(PlayEvent).where(PlayEvent.id.in_(oldest_ids)))
    await session.commit()


async def list_recent_history(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 50,
) -> TrackListResponse:
    stmt = (
        select(PlayEvent)
        .options(selectinload(PlayEvent.track).selectinload(Track.artist))
        .where(PlayEvent.user_id == user.id)
        .order_by(PlayEvent.played_at.desc())
        .limit(limit * 3)
    )
    events = list((await session.execute(stmt)).scalars().all())

    seen: set[UUID] = set()
    tracks: list[TrackSummary] = []
    for event in events:
        if event.track_id in seen:
            continue
        if event.track.published_at is None:
            continue
        seen.add(event.track_id)
        tracks.append(_track_summary(event.track))
        if len(tracks) >= limit:
            break

    return TrackListResponse(items=tracks, total=len(tracks), page=1, page_size=limit)


async def clear_history(session: AsyncSession, user: User) -> None:
    await session.execute(delete(PlayEvent).where(PlayEvent.user_id == user.id))
    await session.commit()


async def remove_track_from_history(
    session: AsyncSession, user: User, track_slug: str
) -> None:
    track = await session.scalar(select(Track).where(Track.slug == track_slug))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    await session.execute(
        delete(PlayEvent).where(
            PlayEvent.user_id == user.id,
            PlayEvent.track_id == track.id,
        )
    )
    await session.commit()
