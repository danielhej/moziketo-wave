from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Tag, TagKind, Track
from app.schemas import BrowseResponse, BrowseSection
from app.services.cache import cache_get, cache_set
from app.services.catalog import _fetch_tracks, _track_summary
from app.services.media import published_track_filter

SECTION_TITLES = {
    "popular": "پربازدید",
    "latest": "جدیدترین",
    "new_release": "تازه‌ها",
}


async def _fetch_new_release_tracks(session: AsyncSession, *, limit: int = 24) -> list[Track]:
    tag_subq = (
        select(Track.id)
        .join(Track.tags)
        .where(Tag.kind == TagKind.STATION_TAG, Tag.slug == "new-release")
        .where(published_track_filter())
    )
    result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .where(Track.id.in_(tag_subq))
        .order_by(Track.published_at.desc())
        .limit(limit)
    )
    tracks = list(result.scalars().unique().all())
    if len(tracks) >= limit:
        return tracks

    seen = {t.id for t in tracks}
    cutoff = datetime.now(UTC) - timedelta(days=90)
    remaining = limit - len(tracks)
    fallback = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .where(published_track_filter(), Track.published_at >= cutoff)
        .where(Track.id.notin_(seen) if seen else True)
        .order_by(Track.published_at.desc())
        .limit(remaining)
    )
    tracks.extend(fallback.scalars().unique().all())
    return tracks


async def get_browse(session: AsyncSession) -> BrowseResponse:
    cache_key = "browse:home"
    cached = await cache_get(cache_key)
    if cached is not None:
        return BrowseResponse.model_validate(cached)

    popular = await _fetch_tracks(session, sort="popular", limit=24)
    latest = await _fetch_tracks(session, sort="latest", limit=24)
    new_release = await _fetch_new_release_tracks(session, limit=24)

    response = BrowseResponse(
        sections=[
            BrowseSection(
                id="popular",
                title=SECTION_TITLES["popular"],
                tracks=[_track_summary(t) for t in popular],
            ),
            BrowseSection(
                id="latest",
                title=SECTION_TITLES["latest"],
                tracks=[_track_summary(t) for t in latest],
            ),
            BrowseSection(
                id="new_release",
                title=SECTION_TITLES["new_release"],
                tracks=[_track_summary(t) for t in new_release],
            ),
        ]
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response
