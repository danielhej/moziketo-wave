from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, Artist, PlayEvent, Track, User
from app.schemas.admin_analytics import (
    AnalyticsOverview,
    RankedArtist,
    RankedTrack,
    TimeSeriesPoint,
    TimeSeriesResponse,
    TopArtistsResponse,
    TopTracksResponse,
)
from app.services.media import published_album_filter, published_track_filter

_PERIOD_RE = re.compile(r"^(\d+)(d|h)$")


def _parse_period(period: str) -> timedelta:
    match = _PERIOD_RE.match(period.strip().lower())
    if not match:
        raise ValueError("Invalid period")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(hours=amount)


def _since(period: str) -> datetime:
    return datetime.now(UTC) - _parse_period(period)


async def get_overview(session: AsyncSession) -> AnalyticsOverview:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    users_total = int((await session.scalar(select(func.count()).select_from(User))) or 0)
    users_active = int(
        (
            await session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
        )
        or 0
    )
    tracks_published = int(
        (
            await session.scalar(
                select(func.count()).select_from(Track).where(published_track_filter())
            )
        )
        or 0
    )
    artists_total = int((await session.scalar(select(func.count()).select_from(Artist))) or 0)
    albums_published = int(
        (
            await session.scalar(
                select(func.count()).select_from(Album).where(published_album_filter())
            )
        )
        or 0
    )
    plays_today = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(PlayEvent)
                .where(PlayEvent.played_at >= day_start)
            )
        )
        or 0
    )
    plays_7d = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(PlayEvent)
                .where(PlayEvent.played_at >= now - timedelta(days=7))
            )
        )
        or 0
    )
    plays_30d = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(PlayEvent)
                .where(PlayEvent.played_at >= now - timedelta(days=30))
            )
        )
        or 0
    )
    streams_total = int(
        (await session.scalar(select(func.coalesce(func.sum(Track.stream_count), 0)))) or 0
    )

    return AnalyticsOverview(
        users_total=users_total,
        users_active=users_active,
        tracks_published=tracks_published,
        artists_total=artists_total,
        albums_published=albums_published,
        plays_today=plays_today,
        plays_7d=plays_7d,
        plays_30d=plays_30d,
        streams_total=streams_total,
    )


async def get_top_tracks(
    session: AsyncSession, *, period: str = "7d", limit: int = 20
) -> TopTracksResponse:
    since = _since(period)
    stmt = (
        select(
            Track.slug,
            Track.title,
            Artist.name,
            func.count(PlayEvent.id).label("play_count"),
        )
        .join(PlayEvent, PlayEvent.track_id == Track.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(PlayEvent.played_at >= since)
        .group_by(Track.slug, Track.title, Artist.name)
        .order_by(func.count(PlayEvent.id).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    items = [
        RankedTrack(slug=row.slug, title=row.title, artist_name=row.name, play_count=row.play_count)
        for row in rows
    ]

    if not items:
        fallback = await session.execute(
            select(Track.slug, Track.title, Artist.name, Track.stream_count)
            .join(Artist, Track.artist_id == Artist.id)
            .where(published_track_filter())
            .order_by(Track.stream_count.desc())
            .limit(limit)
        )
        items = [
            RankedTrack(
                slug=row.slug,
                title=row.title,
                artist_name=row.name,
                play_count=row.stream_count,
            )
            for row in fallback.all()
        ]

    return TopTracksResponse(period=period, items=items)


async def get_top_artists(
    session: AsyncSession, *, period: str = "7d", limit: int = 20
) -> TopArtistsResponse:
    since = _since(period)
    stmt = (
        select(Artist.slug, Artist.name, func.count(PlayEvent.id).label("play_count"))
        .join(Track, Track.artist_id == Artist.id)
        .join(PlayEvent, PlayEvent.track_id == Track.id)
        .where(PlayEvent.played_at >= since)
        .group_by(Artist.slug, Artist.name)
        .order_by(func.count(PlayEvent.id).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    items = [
        RankedArtist(slug=row.slug, name=row.name, play_count=row.play_count) for row in rows
    ]
    return TopArtistsResponse(period=period, items=items)


async def _daily_series(
    session: AsyncSession,
    *,
    period: str,
    model,
    timestamp_column,
) -> TimeSeriesResponse:
    since = _since(period)
    day = func.date_trunc("day", timestamp_column)
    stmt = (
        select(day.label("day"), func.count().label("count"))
        .select_from(model)
        .where(timestamp_column >= since)
        .group_by(day)
        .order_by(day)
    )
    rows = (await session.execute(stmt)).all()
    points = [
        TimeSeriesPoint(
            day=row.day.date() if hasattr(row.day, "date") else row.day,
            count=row.count,
        )
        for row in rows
    ]
    return TimeSeriesResponse(period=period, points=points)


async def get_signups_series(session: AsyncSession, *, period: str = "30d") -> TimeSeriesResponse:
    return await _daily_series(session, period=period, model=User, timestamp_column=User.created_at)


async def get_plays_series(session: AsyncSession, *, period: str = "30d") -> TimeSeriesResponse:
    return await _daily_series(
        session, period=period, model=PlayEvent, timestamp_column=PlayEvent.played_at
    )
