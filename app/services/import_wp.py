"""Import catalog from moziketo.ir WordPress REST API."""

from __future__ import annotations

import argparse
import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Artist, Track
from app.schemas.admin import ImportResult
from app.services.media import extract_wp_media

STATION_ENDPOINTS = (
    "wp/v2/station",
    "wp/v2/stations",
    "wp/v2/posts",
)


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "unknown"


def _parse_artist_name(item: dict[str, Any]) -> tuple[str, str]:
    title = item.get("title", {})
    if isinstance(title, dict):
        title = title.get("rendered", "Unknown")
    meta = item.get("meta") or {}
    artist = meta.get("artist") or meta.get("artist_name") or title
    slug = _slugify(str(artist))
    return str(artist), slug


async def _discover_station_endpoint(client: httpx.AsyncClient, base: str) -> str | None:
    for endpoint in STATION_ENDPOINTS:
        url = f"{base.rstrip('/')}/{endpoint}"
        try:
            resp = await client.get(url, params={"per_page": 1})
            if resp.status_code == 200:
                return endpoint
        except httpx.HTTPError:
            continue
    return None


async def _fetch_page(
    client: httpx.AsyncClient, base: str, endpoint: str, page: int
) -> list[dict[str, Any]]:
    url = f"{base.rstrip('/')}/{endpoint}"
    resp = await client.get(url, params={"per_page": 100, "page": page, "status": "publish"})
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def run_import(
    session: AsyncSession, *, limit: int = 100, dry_run: bool = False
) -> ImportResult:
    settings = get_settings()
    result = ImportResult()

    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoint = await _discover_station_endpoint(client, settings.wp_api_base_url)
        if endpoint is None:
            result.errors.append("Could not discover WP station endpoint")
            return result

        page = 1
        imported = 0
        unlimited = limit == 0
        effective_limit = limit if not unlimited else 10**9
        while imported < effective_limit:
            items = await _fetch_page(client, settings.wp_api_base_url, endpoint, page)
            if not items:
                break

            for item in items:
                if not unlimited and imported >= limit:
                    break
                try:
                    title = item.get("title", {})
                    if isinstance(title, dict):
                        title = title.get("rendered", "Untitled")
                    slug = item.get("slug") or _slugify(str(title))
                    artist_name, artist_slug = _parse_artist_name(item)

                    published_at = None
                    date_str = item.get("date_gmt") or item.get("date")
                    if date_str:
                        published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                    if dry_run:
                        imported += 1
                        continue

                    artist = await session.scalar(select(Artist).where(Artist.slug == artist_slug))
                    if artist is None:
                        artist = Artist(slug=artist_slug, name=artist_name, name_en=artist_slug)
                        session.add(artist)
                        await session.flush()
                        result.artists_upserted += 1

                    meta = item.get("meta") or {}
                    wp_audio, wp_cover, wp_duration = extract_wp_media(meta)
                    if not wp_audio or "dl.moziketo.ir" in wp_audio:
                        result.skipped += 1
                        continue

                    track = await session.scalar(select(Track).where(Track.slug == slug))
                    if track is None:
                        track = Track(
                            slug=slug,
                            title=str(title),
                            artist_id=artist.id,
                            audio_url=wp_audio,
                            cover_url=wp_cover,
                            duration_seconds=wp_duration,
                            published_at=published_at or datetime.now(UTC),
                        )
                        session.add(track)
                        result.tracks_upserted += 1
                    else:
                        track.title = str(title)
                        track.artist_id = artist.id
                        track.audio_url = wp_audio
                        if wp_cover:
                            track.cover_url = wp_cover
                        if wp_duration is not None:
                            track.duration_seconds = wp_duration
                        track.published_at = published_at or track.published_at
                        result.tracks_upserted += 1

                    imported += 1
                except Exception as exc:
                    result.errors.append(str(exc))
                    result.skipped += 1

            page += 1

        if not dry_run:
            await session.commit()

    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import moziketo.ir stations into wave catalog")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    async with SessionLocal() as session:
        result = await run_import(session, limit=args.limit, dry_run=args.dry_run)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
