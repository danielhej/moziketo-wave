"""Parallel moz-downloader prepare — YTM videoId + background yt-dlp resolve."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from pydantic import HttpUrl

from app.schemas.catalog import SearchHit
from app.schemas.downloader import DownloaderPlayRequest
from app.services.cache import cache_set
from app.services.downloader import downloader_configured, get_play_job, start_play

logger = logging.getLogger(__name__)

SPOTIFY_KEY_RE = re.compile(r"^[A-Za-z0-9]{22}$")
PREPARE_POLL_INTERVAL = 0.15
PREPARE_MAX_WAIT = 45.0
PREPARE_WORKERS = 2  # match moz-downloader _resolve_semaphore
PLAY_SESSION_TTL = 3600
YT_READY_TTL = 45 * 60  # match moz-downloader direct URL cache TTL


async def _cache_prepared_session(
    key: str, *, job_id: str, stream_url: str, title: str, artist: str
) -> None:
    session = {
        "job_id": job_id,
        "stream_url": stream_url,
        "title": title,
        "artist": artist,
        "direct_ready": True,
    }
    await cache_set(f"play:session:{key}", session, ttl=PLAY_SESSION_TTL)
    await cache_set(
        f"yt:ready:{key}",
        {"stream_url": stream_url, "title": title, "artist": artist},
        ttl=YT_READY_TTL,
    )


async def prepare_single_hit(
    hit: SearchHit,
    *,
    duration_ms: int | None = None,
    isrc: str | None = None,
    max_wait: float = PREPARE_MAX_WAIT,
) -> SearchHit:
    if hit.in_catalog or not SPOTIFY_KEY_RE.match(hit.key) or not downloader_configured():
        return hit

    try:
        play = await start_play(
            DownloaderPlayRequest(
                spotify_url=HttpUrl(f"https://open.spotify.com/track/{hit.key}"),
                title=hit.title,
                artist=hit.artist_name,
                key=f"{hit.key}.mp3",
                duration_ms=duration_ms,
                isrc=isrc,
                prepare_only=True,
            )
        )
    except Exception:
        logger.debug("prepare start failed for %s", hit.key, exc_info=True)
        hit.play_state = "failed"
        return hit

    hit.job_id = play.job_id
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        try:
            job = await get_play_job(play.job_id)
        except Exception:
            await asyncio.sleep(PREPARE_POLL_INTERVAL)
            continue

        if job.play_ready or job.direct_ready:
            hit.play_state = "ready"
            hit.buffer_bytes = job.buffer_bytes
            await _cache_prepared_session(
                hit.key,
                job_id=play.job_id,
                stream_url=play.stream_url,
                title=play.title,
                artist=play.artist,
            )
            return hit
        if job.status == "failed":
            hit.play_state = "failed"
            hit.buffer_bytes = job.buffer_bytes
            return hit
        await asyncio.sleep(PREPARE_POLL_INTERVAL)

    hit.play_state = "buffering"
    hit.buffer_bytes = 0
    return hit


async def prepare_search_hits(
    hits: list[SearchHit],
    *,
    spotify_meta: dict[str, dict] | None = None,
    max_wait: float = PREPARE_MAX_WAIT,
) -> list[SearchHit]:
    """Prepare all non-catalog Spotify hits (max PREPARE_WORKERS parallel)."""
    if not downloader_configured():
        return hits

    meta = spotify_meta or {}
    targets = [h for h in hits if not h.in_catalog and SPOTIFY_KEY_RE.match(h.key)]
    if not targets:
        return hits

    sem = asyncio.Semaphore(PREPARE_WORKERS)

    async def _one(hit: SearchHit) -> SearchHit:
        async with sem:
            m = meta.get(hit.key) or {}
            return await prepare_single_hit(
                hit,
                duration_ms=m.get("duration_ms"),
                isrc=m.get("isrc"),
                max_wait=max_wait,
            )

    prepared = await asyncio.gather(*[_one(h) for h in targets])
    by_key = {h.key: h for h in prepared}
    return [by_key.get(h.key, h) for h in hits]
