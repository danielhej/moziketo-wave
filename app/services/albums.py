from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Album, Track
from app.schemas.album import AlbumDetail, AlbumListResponse, AlbumSummary
from app.services.cache import cache_get, cache_set
from app.services.catalog import _track_summary
from app.services.media import published_album_filter, resolve_cover_url


def _published_tracks(album: Album) -> list[Track]:
    now = datetime.now(UTC)
    return sorted(
        [
            t
            for t in album.tracks
            if t.published_at is not None and t.published_at <= now
        ],
        key=lambda t: (t.published_at or t.created_at, t.title),
    )


def _album_summary(album: Album) -> AlbumSummary:
    published = _published_tracks(album)
    return AlbumSummary(
        id=str(album.id),
        slug=album.slug,
        title=album.title,
        artist_name=album.artist.name,
        artist_slug=album.artist.slug,
        cover_url=resolve_cover_url(album.slug, album.cover_url),
        track_count=len(published),
    )


def _album_detail(album: Album) -> AlbumDetail:
    published = _published_tracks(album)
    return AlbumDetail(
        id=str(album.id),
        slug=album.slug,
        title=album.title,
        artist_name=album.artist.name,
        artist_slug=album.artist.slug,
        cover_url=resolve_cover_url(album.slug, album.cover_url),
        track_count=len(published),
        description=album.description,
        published_at=album.published_at,
        tracks=[_track_summary(t) for t in published],
    )


async def list_albums(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> AlbumListResponse:
    cache_key = f"albums:list:{page}:{page_size}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return AlbumListResponse.model_validate(cached)

    count_stmt = select(func.count()).select_from(Album).where(published_album_filter())
    total = int((await session.scalar(count_stmt)) or 0)

    offset = (page - 1) * page_size
    stmt = (
        select(Album)
        .options(selectinload(Album.artist), selectinload(Album.tracks))
        .where(published_album_filter())
        .order_by(Album.published_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    albums = list(result.scalars().unique().all())

    response = AlbumListResponse(
        items=[_album_summary(a) for a in albums],
        total=total,
        page=page,
        page_size=page_size,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def get_album(session: AsyncSession, slug: str) -> AlbumDetail:
    cache_key = f"albums:{slug}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return AlbumDetail.model_validate(cached)

    stmt = (
        select(Album)
        .options(selectinload(Album.artist), selectinload(Album.tracks).selectinload(Track.artist))
        .where(Album.slug == slug, published_album_filter())
    )
    album = (await session.execute(stmt)).scalar_one_or_none()
    if album is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    detail = _album_detail(album)
    await cache_set(cache_key, detail.model_dump(mode="json"))
    return detail
