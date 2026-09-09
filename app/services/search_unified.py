"""Spotify-first search merged with local catalog."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Artist, Track
from app.schemas.catalog import ArtistSummary, SearchHit, SearchResponse
from app.services.cache import cache_get, cache_set
from app.services.catalog import (
    _published_track_count_subquery,
    _track_summary,
    published_track_filter,
)
from app.services.spotify import search_tracks as spotify_search
from app.services.spotify import spotify_configured
from app.services.stream_key import cache_preview_url, warm_play_hits


async def _local_tracks(session: AsyncSession, *, q: str, limit: int) -> list[Track]:
    pattern = f"%{q.strip()}%"
    result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .join(Artist)
        .where(
            published_track_filter(),
            or_(
                Track.title.ilike(pattern),
                Track.slug.ilike(pattern),
                Artist.name.ilike(pattern),
                Artist.name_en.ilike(pattern),
                Track.spotify_id.ilike(pattern),
            ),
        )
        .order_by(Track.stream_count.desc(), Track.published_at.desc())
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def _local_artists(session: AsyncSession, *, q: str, limit: int) -> list[tuple[Artist, int]]:
    pattern = f"%{q.strip()}%"
    track_counts = _published_track_count_subquery()
    result = await session.execute(
        select(Artist, func.coalesce(track_counts.c.cnt, 0))
        .outerjoin(track_counts, Artist.id == track_counts.c.artist_id)
        .where(
            or_(
                Artist.name.ilike(pattern),
                Artist.name_en.ilike(pattern),
                Artist.slug.ilike(pattern),
            )
        )
        .order_by(Artist.name)
        .limit(limit)
    )
    return list(result.all())


def _track_to_hit(track: Track) -> SearchHit:
    key = track.spotify_id or track.slug
    return SearchHit(
        key=key,
        title=track.title,
        artist_name=track.artist.name,
        cover_url=track.cover_url,
        duration_seconds=track.duration_seconds,
        in_catalog=True,
        slug=track.slug,
    )


async def unified_search(session: AsyncSession, *, q: str, limit: int = 24) -> SearchResponse:
    query = q.strip()
    limit = min(max(limit, 1), 50)
    cache_key = f"search:unified:{query}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        await warm_play_hits(cached.get("hits") or [], max_wait=8.0)
        return SearchResponse.model_validate(cached)

    catalog_by_spotify: dict[str, Track] = {}
    local_tracks = await _local_tracks(session, q=query, limit=limit)
    for track in local_tracks:
        if track.spotify_id:
            catalog_by_spotify[track.spotify_id] = track

    hits: list[SearchHit] = []
    seen_keys: set[str] = set()

    if spotify_configured():
        for sp in await spotify_search(query, limit=limit):
            in_cat = sp.key in catalog_by_spotify
            track = catalog_by_spotify.get(sp.key)
            if not in_cat and sp.preview_url:
                await cache_preview_url(sp.key, sp.preview_url)
            hits.append(
                SearchHit(
                    key=sp.key,
                    title=track.title if track else sp.title,
                    artist_name=track.artist.name if track else sp.artist_name,
                    cover_url=(track.cover_url if track else None) or sp.cover_url,
                    duration_seconds=track.duration_seconds if track else sp.duration_seconds,
                    in_catalog=in_cat,
                    slug=track.slug if track else None,
                )
            )
            seen_keys.add(sp.key)

    for track in local_tracks:
        hit = _track_to_hit(track)
        if hit.key in seen_keys:
            continue
        hits.append(hit)
        seen_keys.add(hit.key)

    artist_rows = await _local_artists(session, q=query, limit=limit)
    artists = [
        ArtistSummary(
            id=str(artist.id),
            slug=artist.slug,
            name=artist.name,
            name_en=artist.name_en,
            cover_url=artist.cover_url,
            track_count=int(count),
        )
        for artist, count in artist_rows
    ]

    response = SearchResponse(
        query=query,
        hits=hits[:limit],
        tracks=[_track_summary(t) for t in local_tracks],
        artists=artists,
        track_total=len(hits),
        artist_total=len(artists),
    )
    payload = response.model_dump(mode="json")
    await cache_set(cache_key, payload)
    await warm_play_hits(payload.get("hits") or [], max_wait=8.0)
    return response
