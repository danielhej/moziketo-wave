"""Spotify-first search merged with local catalog."""

from __future__ import annotations

import asyncio
import logging
import os

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
from app.services.downloader import downloader_configured
from app.services.prepare_play import kick_prepare_hit
from app.services.spotify import SpotifyTrackHit, spotify_configured
from app.services.spotify import search_tracks as spotify_search
from app.services.stream_key import cache_preview_url

logger = logging.getLogger(__name__)

# Search returns immediately; optional tiny wait for instant cache hits only.
PREPARE_SEARCH_WAIT_SEC = float(os.getenv("PREPARE_SEARCH_WAIT_SEC", "0.3"))
PREPARE_SEARCH_TOP_K = int(os.getenv("PREPARE_SEARCH_TOP_K", "3"))


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


def _spotify_to_hit(
    sp: SpotifyTrackHit,
    *,
    catalog_by_spotify: dict[str, Track],
) -> SearchHit:
    in_cat = sp.key in catalog_by_spotify
    track = catalog_by_spotify.get(sp.key)
    return SearchHit(
        key=sp.key,
        title=track.title if track else sp.title,
        artist_name=track.artist.name if track else sp.artist_name,
        cover_url=(track.cover_url if track else None) or sp.cover_url,
        duration_seconds=track.duration_seconds if track else sp.duration_seconds,
        in_catalog=in_cat,
        slug=track.slug if track else None,
    )


async def unified_search(session: AsyncSession, *, q: str, limit: int = 24) -> SearchResponse:
    query = q.strip()
    limit = min(max(limit, 1), 50)
    cache_key = f"search:unified:{query}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return SearchResponse.model_validate(cached)

    # Spotify + local catalog in parallel
    if spotify_configured():
        local_tracks, sp_results = await asyncio.gather(
            _local_tracks(session, q=query, limit=limit),
            spotify_search(query, limit=limit),
        )
    else:
        local_tracks = await _local_tracks(session, q=query, limit=limit)
        sp_results = []

    catalog_by_spotify: dict[str, Track] = {}
    for track in local_tracks:
        if track.spotify_id:
            catalog_by_spotify[track.spotify_id] = track

    hits: list[SearchHit] = []
    seen_keys: set[str] = set()
    prepare_tasks: list[asyncio.Task[SearchHit]] = []
    prepare_slots = PREPARE_SEARCH_TOP_K

    # Kick prepare for top-K hits only — overlaps with artist query below
    for sp in sp_results:
        hit = _spotify_to_hit(sp, catalog_by_spotify=catalog_by_spotify)
        if not hit.in_catalog and sp.preview_url:
            await cache_preview_url(sp.key, sp.preview_url)
        hits.append(hit)
        seen_keys.add(sp.key)
        if (
            not hit.in_catalog
            and downloader_configured()
            and prepare_slots > 0
        ):
            prepare_slots -= 1
            prepare_tasks.append(
                asyncio.create_task(
                    kick_prepare_hit(
                        hit,
                        duration_ms=sp.duration_ms,
                        isrc=sp.isrc,
                    ),
                    name=f"prepare-{sp.key[:8]}",
                )
            )

    for track in local_tracks:
        hit = _track_to_hit(track)
        if hit.key in seen_keys:
            continue
        hits.append(hit)
        seen_keys.add(hit.key)

    artists_task = asyncio.create_task(_local_artists(session, q=query, limit=limit))

    if prepare_tasks:
        done, _pending = await asyncio.wait(
            prepare_tasks,
            timeout=PREPARE_SEARCH_WAIT_SEC,
        )
        by_key: dict[str, SearchHit] = {}
        for task in done:
            try:
                prepared = task.result()
                by_key[prepared.key] = prepared
            except Exception:
                logger.debug("prepare task failed during search", exc_info=True)
        hits = [by_key.get(h.key, h) for h in hits]

    artist_rows = await artists_task
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
    await cache_set(cache_key, payload, ttl=300)
    return response
