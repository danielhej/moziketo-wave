
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Artist, Track
from app.schemas import (
    ArtistDetail,
    ArtistListResponse,
    ArtistSummary,
    SearchResponse,
    TrackDetail,
    TrackListResponse,
    TrackSummary,
)
from app.services.cache import cache_get, cache_set
from app.services.media import (
    apply_published_filter,
    published_track_filter,
    resolve_audio_url,
    resolve_cover_url,
)

_trgm_available: bool | None = None


def _track_summary(track: Track) -> TrackSummary:
    return TrackSummary(
        id=str(track.id),
        slug=track.slug,
        title=track.title,
        artist_name=track.artist.name,
        duration_seconds=track.duration_seconds,
        cover_url=resolve_cover_url(track.slug, track.cover_url),
    )


def _track_detail(track: Track) -> TrackDetail:
    return TrackDetail(
        id=str(track.id),
        slug=track.slug,
        title=track.title,
        artist_name=track.artist.name,
        artist_slug=track.artist.slug,
        duration_seconds=track.duration_seconds,
        cover_url=resolve_cover_url(track.slug, track.cover_url),
        audio_url=resolve_audio_url(track.slug, track.audio_url),
        description=track.description,
    )


def _published_track_count_subquery():
    return (
        select(Track.artist_id, func.count().label("cnt"))
        .where(published_track_filter())
        .group_by(Track.artist_id)
        .subquery()
    )


async def _check_trgm(session: AsyncSession) -> bool:
    global _trgm_available
    if _trgm_available is not None:
        return _trgm_available
    result = await session.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm' LIMIT 1")
    )
    _trgm_available = result.scalar_one_or_none() is not None
    return _trgm_available


async def list_tracks(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> TrackListResponse:
    cache_key = f"tracks:list:{page}:{page_size}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return TrackListResponse.model_validate(cached)

    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    count_stmt = select(func.count()).select_from(Track).where(published_track_filter())
    total = await session.scalar(count_stmt) or 0

    stmt = apply_published_filter(
        select(Track)
        .options(selectinload(Track.artist))
        .order_by(Track.published_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    tracks = result.scalars().all()

    response = TrackListResponse(
        items=[_track_summary(t) for t in tracks],
        total=total,
        page=page,
        page_size=page_size,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def get_track(session: AsyncSession, slug: str) -> TrackDetail:
    cache_key = f"tracks:{slug}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return TrackDetail.model_validate(cached)

    result = await session.execute(
        apply_published_filter(
            select(Track).options(selectinload(Track.artist)).where(Track.slug == slug)
        )
    )
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    response = _track_detail(track)
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def get_published_track(session: AsyncSession, slug: str) -> Track:
    result = await session.execute(
        apply_published_filter(
            select(Track).options(selectinload(Track.artist)).where(Track.slug == slug)
        )
    )
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    return track


async def resolve_stream_url(session: AsyncSession, slug: str) -> str:
    track = await get_published_track(session, slug)
    url = resolve_audio_url(track.slug, track.audio_url)
    if not url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not available")
    return url


async def list_artists(
    session: AsyncSession, *, page: int = 1, page_size: int = 24
) -> ArtistListResponse:
    cache_key = f"artists:list:{page}:{page_size}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return ArtistListResponse.model_validate(cached)

    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    total = await session.scalar(select(func.count()).select_from(Artist)) or 0
    track_counts = _published_track_count_subquery()
    result = await session.execute(
        select(Artist, func.coalesce(track_counts.c.cnt, 0))
        .outerjoin(track_counts, Artist.id == track_counts.c.artist_id)
        .order_by(Artist.name)
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    response = ArtistListResponse(
        items=[
            ArtistSummary(
                id=str(artist.id),
                slug=artist.slug,
                name=artist.name,
                name_en=artist.name_en,
                cover_url=artist.cover_url,
                track_count=int(count),
            )
            for artist, count in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def get_artist(session: AsyncSession, slug: str) -> ArtistDetail:
    cache_key = f"artists:{slug}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return ArtistDetail.model_validate(cached)

    result = await session.execute(
        select(Artist).options(selectinload(Artist.tracks)).where(Artist.slug == slug)
    )
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")

    published = [
        t
        for t in artist.tracks
        if t.published_at is not None and t.published_at <= datetime.now(UTC)
    ]
    published.sort(key=lambda t: t.published_at or t.created_at, reverse=True)

    response = ArtistDetail(
        id=str(artist.id),
        slug=artist.slug,
        name=artist.name,
        name_en=artist.name_en,
        cover_url=artist.cover_url,
        track_count=len(published),
        bio=artist.bio,
        tracks=[_track_summary(t) for t in published],
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(select(1))
        return True
    except Exception:
        return False


async def search_catalog(
    session: AsyncSession,
    *,
    q: str,
    limit: int = 24,
) -> SearchResponse:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query must be at least 2 characters",
        )

    limit = min(max(limit, 1), 50)
    cache_key = f"search:{query}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return SearchResponse.model_validate(cached)

    use_trgm = await _check_trgm(session)
    pattern = f"%{query}%"

    if use_trgm:
        track_filter = or_(
            func.similarity(Track.title, query) > 0.1,
            func.similarity(Track.slug, query) > 0.1,
            func.similarity(Artist.name, query) > 0.1,
            func.similarity(Artist.name_en, query) > 0.1,
        )
        track_order = func.greatest(
            func.similarity(Track.title, query),
            func.similarity(Artist.name, query),
        ).desc()
        artist_filter = or_(
            func.similarity(Artist.name, query) > 0.1,
            func.similarity(Artist.name_en, query) > 0.1,
            func.similarity(Artist.slug, query) > 0.1,
        )
        artist_order = func.similarity(Artist.name, query).desc()
    else:
        track_filter = or_(
            Track.title.ilike(pattern),
            Track.slug.ilike(pattern),
            Artist.name.ilike(pattern),
            Artist.name_en.ilike(pattern),
        )
        track_order = Track.created_at.desc()
        artist_filter = or_(
            Artist.name.ilike(pattern),
            Artist.name_en.ilike(pattern),
            Artist.slug.ilike(pattern),
        )
        artist_order = Artist.name

    track_total = await session.scalar(
        select(func.count())
        .select_from(Track)
        .join(Artist)
        .where(published_track_filter(), track_filter)
    ) or 0

    track_result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .join(Artist)
        .where(published_track_filter(), track_filter)
        .order_by(track_order)
        .limit(limit)
    )
    tracks = track_result.scalars().unique().all()

    artist_total = await session.scalar(
        select(func.count()).select_from(Artist).where(artist_filter)
    ) or 0

    track_counts = _published_track_count_subquery()
    artist_result = await session.execute(
        select(Artist, func.coalesce(track_counts.c.cnt, 0))
        .outerjoin(track_counts, Artist.id == track_counts.c.artist_id)
        .where(artist_filter)
        .order_by(artist_order)
        .limit(limit)
    )
    artist_rows = artist_result.all()

    response = SearchResponse(
        query=query,
        tracks=[_track_summary(t) for t in tracks],
        artists=[
            ArtistSummary(
                id=str(artist.id),
                slug=artist.slug,
                name=artist.name,
                name_en=artist.name_en,
                cover_url=artist.cover_url,
                track_count=int(count),
            )
            for artist, count in artist_rows
        ],
        track_total=track_total,
        artist_total=artist_total,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response
