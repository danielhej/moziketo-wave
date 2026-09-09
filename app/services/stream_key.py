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
from app.services.cache import cache_get, cache_set
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
WARM_MAX_WAIT = 25.0
CLICK_MAX_WAIT = 2.0


async def cache_preview_url(key: str, preview_url: str | None) -> None:
    if preview_url:
        await cache_set(f"preview:{key}", preview_url, ttl=PREVIEW_CACHE_TTL)


async def cache_direct_url(key: str, url: str, media_type: str) -> None:
    await cache_set(
        f"yt:direct:{key}",
        {"url": url, "media_type": media_type},
        ttl=YT_DIRECT_TTL,
    )


async def get_cached_direct(key: str) -> dict | None:
    return await cache_get(f"yt:direct:{key}")


async def _sync_direct_from_job(key: str, job_id: str) -> dict | None:
    try:
        job = await get_play_job(job_id)
    except Exception:
        return None
    if not job.direct_ready or not job.direct_stream_url:
        return None
    media_type = job.direct_media_type or "audio/mp4"
    await cache_direct_url(key, job.direct_stream_url, media_type)
    return {"url": job.direct_stream_url, "media_type": media_type}


async def _proxy_cached_direct(
    direct: dict,
    *,
    range_header: str | None,
    filename: str,
) -> StreamingResponse:
    return await proxy_audio(
        direct["url"],
        range_header=range_header,
        filename=filename,
    )


async def _wait_for_direct_ready(
    job_id: str, *, max_wait: float = WARM_MAX_WAIT
) -> bool:
    """Poll moz-downloader until YouTube CDN URL is resolved."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        try:
            job = await get_play_job(job_id)
        except Exception:
            await asyncio.sleep(WARM_POLL_INTERVAL)
            continue
        if job.status == "failed":
            return False
        if job.direct_ready:
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
    if await get_cached_direct(key):
        return True
    await cache_preview_url(key, preview_url)
    cached = await cache_get(f"play:session:{key}")
    if cached and cached.get("direct_ready"):
        await _sync_direct_from_job(key, cached["job_id"])
        return True
    try:
        session = cached or await _get_play_session(
            key, title_hint=title, artist_hint=artist
        )
        ready = await _wait_for_direct_ready(session["job_id"], max_wait=max_wait)
        session["direct_ready"] = ready
        if ready:
            await _sync_direct_from_job(key, session["job_id"])
        await cache_set(f"play:session:{key}", session, ttl=PLAY_SESSION_TTL)
        return ready
    except Exception:
        logger.debug("warm play failed for %s", key, exc_info=True)
        return False


async def warm_play_hits(hits: list[dict], *, max_wait: float = WARM_MAX_WAIT) -> None:
    for hit in hits:
        if hit.get("in_catalog"):
            continue
        key = hit.get("key", "")
        if not SPOTIFY_KEY_RE.match(key):
            continue
        await warm_play_hit(
            key,
            title=hit.get("title") or "",
            artist=hit.get("artist_name") or "",
            preview_url=hit.get("preview_url"),
            max_wait=max_wait,
        )
        break


async def warm_track(
    key: str,
    *,
    title: str | None = None,
    artist: str | None = None,
) -> dict:
    """Explicit warm before play click — call when track row is visible."""
    if not SPOTIFY_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key")
    direct = await get_cached_direct(key)
    if direct:
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


async def _stream_spotify_hit(
    key: str,
    *,
    range_header: str | None,
    title_hint: str | None,
    artist_hint: str | None,
) -> StreamingResponse:
    """Click path: cached CDN → wait 2s → preview fallback → downloader proxy."""
    direct = await get_cached_direct(key)
    if direct:
        name = slugify(artist_hint or "track")
        return await _proxy_cached_direct(
            direct, range_header=range_header, filename=f"{name}.mp3"
        )

    play_session = await _get_play_session(
        key, title_hint=title_hint, artist_hint=artist_hint
    )
    asyncio.create_task(
        _background_ingest(
            key,
            play_session["job_id"],
            play_session["title"],
            play_session["artist"],
            play_session.get("cover_url"),
        )
    )

    if play_session.get("direct_ready"):
        synced = await _sync_direct_from_job(key, play_session["job_id"])
        if synced:
            filename = f"{slugify(play_session['artist'])}-{slugify(play_session['title'])}.mp3"
            return await _proxy_cached_direct(
                synced, range_header=range_header, filename=filename
            )

    ready = await _wait_for_direct_ready(
        play_session["job_id"], max_wait=CLICK_MAX_WAIT
    )
    if ready:
        synced = await _sync_direct_from_job(key, play_session["job_id"])
        play_session["direct_ready"] = True
        await cache_set(f"play:session:{key}", play_session, ttl=PLAY_SESSION_TTL)
        if synced:
            filename = f"{slugify(play_session['artist'])}-{slugify(play_session['title'])}.mp3"
            return await _proxy_cached_direct(
                synced, range_header=range_header, filename=filename
            )

    preview_url = play_session.get("preview_url") or await cache_get(f"preview:{key}")
    if preview_url:
        filename = f"{slugify(play_session['artist'])}-preview.mp3"
        return await proxy_audio(preview_url, range_header=range_header, filename=filename)

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
