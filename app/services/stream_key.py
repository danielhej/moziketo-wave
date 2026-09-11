"""Unified stream by key (Spotify track id or catalog slug)."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import UTC, datetime

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import Artist, Track
from app.schemas.downloader import DownloaderPlayRequest
from app.services.audio_proxy import proxy_audio
from app.services.cache import cache_delete, cache_get, cache_set
from app.services.downloader import downloader_configured, get_play_job, start_play
from app.services.import_catalog import slugify
from app.services.media import published_track_filter, resolve_audio_url
from app.services.spotify import fetch_track
from app.services.storage import resolve_media_url

logger = logging.getLogger(__name__)

SPOTIFY_KEY_RE = re.compile(r"^[A-Za-z0-9]{22}$")
PLAY_SESSION_TTL = 3600
PREVIEW_CACHE_TTL = 86400
YT_DIRECT_TTL = 4 * 3600
WARM_POLL_INTERVAL = 0.15
WARM_MAX_WAIT = 45.0


async def cache_preview_url(key: str, preview_url: str | None) -> None:
    if preview_url:
        await cache_set(f"preview:{key}", preview_url, ttl=PREVIEW_CACHE_TTL)


async def cache_play_ready(key: str, session: dict) -> None:
    """Cache downloader proxy URL — wave cannot reach googlevideo directly."""
    await cache_set(
        f"yt:ready:{key}",
        {
            "stream_url": session["stream_url"],
            "title": session["title"],
            "artist": session["artist"],
        },
        ttl=45 * 60,
    )


async def get_cached_play_ready(key: str) -> dict | None:
    return await cache_get(f"yt:ready:{key}")


async def _mark_play_ready(key: str, session: dict) -> dict:
    session["direct_ready"] = True
    await cache_play_ready(key, session)
    await cache_set(f"play:session:{key}", session, ttl=PLAY_SESSION_TTL)
    return session


async def _wait_for_play_ready(
    job_id: str, *, max_wait: float = WARM_MAX_WAIT
) -> bool:
    """Poll moz-downloader until yt-dlp resolved a CDN URL (play_ready)."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        try:
            job = await get_play_job(job_id)
        except Exception:
            await asyncio.sleep(WARM_POLL_INTERVAL)
            continue
        if job.status == "failed":
            return False
        if job.play_ready or job.direct_ready:
            return True
        await asyncio.sleep(WARM_POLL_INTERVAL)
    return False


async def warm_play_hit(
    key: str,
    *,
    title: str,
    artist: str,
    preview_url: str | None = None,
    max_wait: float = WARM_MAX_WAIT,
) -> bool:
    """Prefetch YouTube CDN URL so click-to-play stays under CLICK_MAX_WAIT."""
    if not SPOTIFY_KEY_RE.match(key) or not downloader_configured():
        return False
    if await get_cached_play_ready(key):
        return True
    await cache_preview_url(key, preview_url)
    cached = await cache_get(f"play:session:{key}")
    if cached and cached.get("direct_ready"):
        await cache_play_ready(key, cached)
        return True
    try:
        session = cached or await _get_play_session(
            key, title_hint=title, artist_hint=artist
        )
        ready = await _wait_for_play_ready(session["job_id"], max_wait=max_wait)
        if ready:
            await _mark_play_ready(key, session)
        else:
            session["direct_ready"] = False
            await cache_set(f"play:session:{key}", session, ttl=PLAY_SESSION_TTL)
        return ready
    except Exception:
        logger.debug("warm play failed for %s", key, exc_info=True)
        return False


async def warm_play_hits(hits: list[dict], *, max_wait: float = WARM_MAX_WAIT) -> None:
    tasks: list[asyncio.Task[bool]] = []
    for hit in hits:
        if hit.get("in_catalog"):
            continue
        key = hit.get("key", "")
        if not SPOTIFY_KEY_RE.match(key):
            continue
        tasks.append(
            asyncio.create_task(
                warm_play_hit(
                    key,
                    title=hit.get("title") or "",
                    artist=hit.get("artist_name") or "",
                    preview_url=hit.get("preview_url"),
                    max_wait=max_wait,
                )
            )
        )
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def warm_track(
    key: str,
    *,
    title: str | None = None,
    artist: str | None = None,
) -> dict:
    """Explicit warm before play click — call when track row is visible."""
    if not SPOTIFY_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key")
    ready = await get_cached_play_ready(key)
    if ready:
        return {"status": "ready", "source": "cache"}
    session = await cache_get(f"play:session:{key}")
    if session and session.get("direct_ready"):
        return {"status": "ready", "source": "session"}
    if not downloader_configured():
        return {"status": "unavailable"}
    asyncio.create_task(
        warm_play_hit(
            key,
            title=title or "",
            artist=artist or "",
            max_wait=WARM_MAX_WAIT,
        )
    )
    return {"status": "warming"}


async def _find_catalog_track(session: AsyncSession, key: str) -> Track | None:
    if SPOTIFY_KEY_RE.match(key):
        result = await session.execute(
            select(Track)
            .where(Track.spotify_id == key)
            .where(published_track_filter())
        )
        track = result.scalar_one_or_none()
        if track is not None:
            return track
    result = await session.execute(
        select(Track).where(Track.slug == key).where(published_track_filter())
    )
    return result.scalar_one_or_none()


async def _catalog_stream(
    session: AsyncSession,
    track: Track,
    *,
    range_header: str | None,
) -> StreamingResponse:
    url = resolve_audio_url(track.slug, track.audio_url)
    if not url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not available")
    await session.execute(
        update(Track).where(Track.id == track.id).values(stream_count=Track.stream_count + 1)
    )
    await session.commit()
    resolved = await resolve_media_url(url)
    filename = f"{track.slug}.mp3"
    return await proxy_audio(resolved, range_header=range_header, filename=filename)


async def _get_play_session(
    key: str,
    *,
    title_hint: str | None = None,
    artist_hint: str | None = None,
) -> dict:
    cached = await cache_get(f"play:session:{key}")
    if cached:
        return cached

    spotify_url = f"https://open.spotify.com/track/{key}"
    meta = None
    if not (title_hint and artist_hint):
        meta = await fetch_track(key)
    title = title_hint or (meta.title if meta else None)
    artist = artist_hint or (meta.artist_name if meta else None)
    play = await start_play(
        DownloaderPlayRequest(
            spotify_url=spotify_url,
            title=title,
            artist=artist,
            key=f"{key}.mp3",
            prepare_only=True,
        )
    )
    preview_url = None
    if meta and meta.preview_url:
        preview_url = meta.preview_url
    session_data = {
        "job_id": play.job_id,
        "stream_url": play.stream_url,
        "title": play.title,
        "artist": play.artist,
        "cover_url": meta.cover_url if meta else None,
        "preview_url": preview_url,
        "direct_ready": False,
    }
    if preview_url:
        await cache_set(f"preview:{key}", preview_url, ttl=PREVIEW_CACHE_TTL)
    await cache_set(f"play:session:{key}", session_data, ttl=PLAY_SESSION_TTL)
    return session_data


async def _background_ingest(
    key: str, job_id: str, title: str, artist: str, cover_url: str | None
) -> None:
    try:
        for _ in range(120):
            job = await get_play_job(job_id)
            if job.status == "ready":
                audio_url = job.presigned_url or job.download_url
                break
            if job.status == "failed":
                logger.warning("ingest job failed for %s: %s", key, job.error)
                return
            await asyncio.sleep(2)
        else:
            logger.warning("ingest job timed out for %s", key)
            return

        async with SessionLocal() as session:
            existing = await session.scalar(select(Track).where(Track.spotify_id == key))
            if existing is not None:
                if not existing.audio_url and audio_url:
                    existing.audio_url = audio_url
                    await session.commit()
                return

            artist_slug = slugify(artist)
            db_artist = await session.scalar(select(Artist).where(Artist.slug == artist_slug))
            if db_artist is None:
                db_artist = Artist(
                    slug=artist_slug,
                    name=artist,
                    name_en=artist_slug,
                    cover_url=cover_url,
                )
                session.add(db_artist)
                await session.flush()

            slug = slugify(f"{artist}-{title}")[:180] or key
            taken = await session.scalar(select(Track).where(Track.slug == slug))
            if taken is not None:
                slug = f"{slug}-{key[:8]}"

            track = Track(
                slug=slug,
                spotify_id=key,
                title=title,
                artist_id=db_artist.id,
                cover_url=cover_url,
                audio_url=audio_url,
                published_at=datetime.now(UTC),
            )
            session.add(track)
            await session.commit()
            logger.info("ingested track spotify_id=%s slug=%s", key, slug)
    except Exception:
        logger.exception("background ingest failed for %s", key)


def _is_downloader_stream_url(url: str) -> bool:
    return "/v1/stream/" in url and "googlevideo.com" not in url


async def _stream_spotify_hit(
    key: str,
    *,
    range_header: str | None,
    title_hint: str | None,
    artist_hint: str | None,
) -> StreamingResponse:
    """Click → immediate chunked stream via moz-downloader (pipe or CDN)."""
    cached = await get_cached_play_ready(key)
    if cached and _is_downloader_stream_url(cached.get("stream_url", "")):
        filename = f"{slugify(cached['artist'])}-{slugify(cached['title'])}.mp3"
        try:
            return await proxy_audio(
                cached["stream_url"], range_header=range_header, filename=filename
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_502_BAD_GATEWAY:
                raise
            logger.info("stale stream cache for %s, re-resolving", key)
            await cache_delete(f"yt:ready:{key}")
            await cache_delete(f"play:session:{key}")

    play_session = await _get_play_session(
        key, title_hint=title_hint, artist_hint=artist_hint
    )
    if not play_session.get("direct_ready"):

        async def _cache_when_ready() -> None:
            if await _wait_for_play_ready(
                play_session["job_id"], max_wait=WARM_MAX_WAIT
            ):
                await _mark_play_ready(key, play_session)

        asyncio.create_task(_cache_when_ready())

    asyncio.create_task(
        _background_ingest(
            key,
            play_session["job_id"],
            play_session["title"],
            play_session["artist"],
            play_session.get("cover_url"),
        )
    )

    filename = f"{slugify(play_session['artist'])}-{slugify(play_session['title'])}.mp3"
    return await proxy_audio(
        play_session["stream_url"],
        range_header=range_header,
        filename=filename,
    )


async def resolve_stream(
    session: AsyncSession,
    key: str,
    *,
    range_header: str | None = None,
    title_hint: str | None = None,
    artist_hint: str | None = None,
) -> StreamingResponse:
    key = key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key")

    track = await _find_catalog_track(session, key)
    if track is not None and resolve_audio_url(track.slug, track.audio_url):
        return await _catalog_stream(session, track, range_header=range_header)

    if not SPOTIFY_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    if not downloader_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stream service unavailable",
        )

    return await _stream_spotify_hit(
        key,
        range_header=range_header,
        title_hint=title_hint,
        artist_hint=artist_hint,
    )
