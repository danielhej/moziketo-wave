from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Favorite, Track, User
from app.schemas import TrackListResponse, TrackSummary
from app.services.catalog import _track_summary
from app.services.media import published_track_filter


async def list_favorites(
    session: AsyncSession,
    user: User,
    *,
    page: int = 1,
    page_size: int = 24,
) -> TrackListResponse:
    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    total = (
        await session.scalar(
            select(func.count())
            .select_from(Favorite)
            .join(Track, Favorite.track_id == Track.id)
            .where(Favorite.user_id == user.id)
            .where(published_track_filter())
        )
        or 0
    )

    result = await session.execute(
        select(Track)
        .join(Favorite, Favorite.track_id == Track.id)
        .options(selectinload(Track.artist))
        .where(Favorite.user_id == user.id)
        .where(published_track_filter())
        .order_by(Favorite.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    tracks = result.scalars().unique().all()

    return TrackListResponse(
        items=[_track_summary(t) for t in tracks],
        total=total,
        page=page,
        page_size=page_size,
    )


async def add_favorite(session: AsyncSession, user: User, track_slug: str) -> TrackSummary:
    result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .where(Track.slug == track_slug)
        .where(published_track_filter())
    )
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    existing = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.track_id == track.id)
    )
    if existing is None:
        session.add(Favorite(user_id=user.id, track_id=track.id))
        await session.commit()

    return _track_summary(track)


async def remove_favorite(session: AsyncSession, user: User, track_slug: str) -> None:
    result = await session.execute(select(Track).where(Track.slug == track_slug))
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    fav = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.track_id == track.id)
    )
    if fav is not None:
        await session.delete(fav)
        await session.commit()
