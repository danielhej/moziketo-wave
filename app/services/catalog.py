
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Artist, Track
from app.schemas import (
    ArtistDetail,
    ArtistListResponse,
    ArtistSummary,
    TrackDetail,
    TrackListResponse,
    TrackSummary,
)


def _track_summary(track: Track) -> TrackSummary:
    return TrackSummary(
        id=str(track.id),
        slug=track.slug,
        title=track.title,
        artist_name=track.artist.name,
        duration_seconds=track.duration_seconds,
        cover_url=track.cover_url,
    )


async def list_tracks(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> TrackListResponse:
    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    total = await session.scalar(select(func.count()).select_from(Track)) or 0
    result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .order_by(Track.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    tracks = result.scalars().all()

    return TrackListResponse(
        items=[_track_summary(t) for t in tracks],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_track(session: AsyncSession, slug: str) -> TrackDetail:
    result = await session.execute(
        select(Track).options(selectinload(Track.artist)).where(Track.slug == slug)
    )
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    return TrackDetail(
        id=str(track.id),
        slug=track.slug,
        title=track.title,
        artist_name=track.artist.name,
        artist_slug=track.artist.slug,
        duration_seconds=track.duration_seconds,
        cover_url=track.cover_url,
        audio_url=track.audio_url,
        description=track.description,
    )


async def list_artists(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> ArtistListResponse:
    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    total = await session.scalar(select(func.count()).select_from(Artist)) or 0
    track_counts = (
        select(Track.artist_id, func.count().label("cnt")).group_by(Track.artist_id).subquery()
    )
    result = await session.execute(
        select(Artist, func.coalesce(track_counts.c.cnt, 0))
        .outerjoin(track_counts, Artist.id == track_counts.c.artist_id)
        .order_by(Artist.name)
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    items = [
        ArtistSummary(
            id=str(artist.id),
            slug=artist.slug,
            name=artist.name,
            name_en=artist.name_en,
            cover_url=artist.cover_url,
            track_count=int(count),
        )
        for artist, count in rows
    ]

    return ArtistListResponse(items=items, total=total, page=page, page_size=page_size)


async def get_artist(session: AsyncSession, slug: str) -> ArtistDetail:
    result = await session.execute(
        select(Artist).options(selectinload(Artist.tracks)).where(Artist.slug == slug)
    )
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")

    tracks = sorted(artist.tracks, key=lambda t: t.created_at, reverse=True)
    return ArtistDetail(
        id=str(artist.id),
        slug=artist.slug,
        name=artist.name,
        name_en=artist.name_en,
        cover_url=artist.cover_url,
        track_count=len(tracks),
        bio=artist.bio,
        tracks=[_track_summary(t) for t in tracks],
    )


async def check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(select(1))
        return True
    except Exception:
        return False
