from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Favorite, PlayEvent, Track, User
from app.schemas.browse import BrowseResponse, BrowseSection
from app.schemas.catalog import TrackSummary
from app.services.browse import get_browse
from app.services.cache import cache_get, cache_set
from app.services.catalog import _track_summary
from app.services.media import published_track_filter


def _score_track(
    track: Track,
    *,
    artist_ids: set[UUID],
    tag_ids: set[UUID],
) -> int:
    score = min(track.stream_count // 100, 5)
    if track.artist_id in artist_ids:
        score += 3
    overlap = sum(1 for tag in track.tags if tag.id in tag_ids)
    score += overlap * 2
    return score


async def _user_signals(
    session: AsyncSession, user: User
) -> tuple[set[UUID], set[UUID], set[UUID]]:
    since = datetime.now(UTC) - timedelta(days=30)
    events = await session.scalars(
        select(PlayEvent)
        .options(selectinload(PlayEvent.track).selectinload(Track.tags))
        .where(PlayEvent.user_id == user.id, PlayEvent.played_at >= since)
        .order_by(PlayEvent.played_at.desc())
        .limit(30)
    )
    favorites = await session.scalars(
        select(Favorite)
        .options(selectinload(Favorite.track).selectinload(Track.tags))
        .where(Favorite.user_id == user.id)
    )

    artist_ids: set[UUID] = set()
    tag_ids: set[UUID] = set()
    exclude_track_ids: set[UUID] = set()

    for event in events:
        exclude_track_ids.add(event.track_id)
        artist_ids.add(event.track.artist_id)
        tag_ids.update(tag.id for tag in event.track.tags)

    for fav in favorites:
        exclude_track_ids.add(fav.track_id)
        artist_ids.add(fav.track.artist_id)
        tag_ids.update(tag.id for tag in fav.track.tags)

    return artist_ids, tag_ids, exclude_track_ids


async def get_user_recommendations(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 24,
) -> BrowseResponse:
    cache_key = f"reco:{user.id}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return BrowseResponse.model_validate(cached)

    artist_ids, tag_ids, exclude_ids = await _user_signals(session, user)

    stmt = (
        select(Track)
        .options(selectinload(Track.artist), selectinload(Track.tags))
        .where(published_track_filter())
        .limit(200)
    )
    candidates = list((await session.execute(stmt)).scalars().unique().all())

    scored: list[tuple[int, Track]] = []
    for track in candidates:
        if track.id in exclude_ids:
            continue
        scored.append((_score_track(track, artist_ids=artist_ids, tag_ids=tag_ids), track))

    def _sort_key(item: tuple[int, Track]) -> tuple:
        track = item[1]
        published = track.published_at or datetime.min.replace(tzinfo=UTC)
        return (-item[0], track.stream_count, published)

    scored.sort(key=_sort_key)
    picks = [_track_summary(track) for _, track in scored[:limit]]

    if len(picks) < limit:
        browse = await get_browse(session)
        seen = {p.slug for p in picks} | {
            t.slug for section in browse.sections for t in section.tracks
        }
        for section in browse.sections:
            for track in section.tracks:
                if track.slug in seen:
                    continue
                picks.append(track)
                seen.add(track.slug)
                if len(picks) >= limit:
                    break
            if len(picks) >= limit:
                break

    response = BrowseResponse(
        sections=[
            BrowseSection(id="for_you", title="برای شما", tracks=picks[:limit]),
        ]
    )
    await cache_set(cache_key, response.model_dump(mode="json"), ttl=60)
    return response


async def get_similar_tracks(
    session: AsyncSession, slug: str, *, limit: int = 12
) -> list[TrackSummary]:
    track = await session.scalar(
        select(Track)
        .options(selectinload(Track.tags), selectinload(Track.artist))
        .where(Track.slug == slug, published_track_filter())
    )
    if track is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    tag_ids = {tag.id for tag in track.tags}
    stmt = (
        select(Track)
        .options(selectinload(Track.artist), selectinload(Track.tags))
        .where(published_track_filter(), Track.id != track.id)
        .limit(100)
    )
    candidates = list((await session.execute(stmt)).scalars().unique().all())

    scored: list[tuple[int, Track]] = []
    for candidate in candidates:
        score = 0
        if candidate.artist_id == track.artist_id:
            score += 3
        score += sum(1 for tag in candidate.tags if tag.id in tag_ids) * 2
        score += min(candidate.stream_count // 100, 3)
        if score > 0:
            scored.append((score, candidate))

    scored.sort(key=lambda item: (-item[0], item[1].stream_count))
    return [_track_summary(t) for _, t in scored[:limit]]
