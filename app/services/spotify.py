"""Spotify Web API — client credentials search."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

_token_cache: dict[str, float | str] = {}


@dataclass(frozen=True)
class SpotifyTrackHit:
    key: str
    title: str
    artist_name: str
    cover_url: str | None
    duration_seconds: int | None
    duration_ms: int | None = None
    isrc: str | None = None
    preview_url: str | None = None


def spotify_configured() -> bool:
    settings = get_settings()
    return bool(settings.spotify_client_id.strip() and settings.spotify_client_secret.strip())


async def _get_token() -> str | None:
    if not spotify_configured():
        return None
    settings = get_settings()
    cached = _token_cache.get("access_token")
    expires = float(_token_cache.get("expires_at", 0))
    if isinstance(cached, str) and time.time() < expires - 60:
        return cached

    auth = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
        )
    if response.status_code >= 400:
        return None
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        return None
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = time.time() + int(payload.get("expires_in", 3600))
    return token


async def search_tracks(q: str, *, limit: int = 20) -> list[SpotifyTrackHit]:
    token = await _get_token()
    if not token:
        return []

    params = {
        "q": q.strip(),
        "type": "track",
        "limit": min(max(limit, 1), 50),
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://api.spotify.com/v1/search",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        return []

    items = response.json().get("tracks", {}).get("items", [])
    hits: list[SpotifyTrackHit] = []
    for item in items:
        track_id = item.get("id")
        if not track_id:
            continue
        artists = item.get("artists") or []
        artist_name = artists[0].get("name", "") if artists else ""
        images = item.get("album", {}).get("images") or []
        cover = images[0].get("url") if images else None
        duration_ms = item.get("duration_ms") or None
        hits.append(
            SpotifyTrackHit(
                key=track_id,
                title=str(item.get("name") or ""),
                artist_name=artist_name,
                cover_url=cover,
                duration_seconds=(duration_ms or 0) // 1000 or None,
                duration_ms=duration_ms,
                isrc=(item.get("external_ids") or {}).get("isrc"),
                preview_url=item.get("preview_url"),
            )
        )
    return hits


async def fetch_track(key: str) -> SpotifyTrackHit | None:
    token = await _get_token()
    if not token:
        return None
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.spotify.com/v1/tracks/{key}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        return None
    item = response.json()
    artists = item.get("artists") or []
    images = item.get("album", {}).get("images") or []
    duration_ms = item.get("duration_ms") or None
    return SpotifyTrackHit(
        key=key,
        title=str(item.get("name") or ""),
        artist_name=artists[0].get("name", "") if artists else "",
        cover_url=images[0].get("url") if images else None,
        duration_seconds=(duration_ms or 0) // 1000 or None,
        duration_ms=duration_ms,
        isrc=(item.get("external_ids") or {}).get("isrc"),
        preview_url=item.get("preview_url"),
    )
