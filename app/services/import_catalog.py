"""Import catalog from WP JSON export (tracks, artists, playlists, taxonomy)."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artist, Playlist, PlaylistKind, PlaylistTrack, Tag, TagKind, Track
from app.schemas.admin import ImportResult
from app.services.cache import cache_delete_pattern


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "unknown"


def _parse_tags(item: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return list of (slug, name, kind) from export item."""
    tags: list[tuple[str, str, str]] = []

    raw_tags = item.get("tags")
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, dict):
                kind = str(t.get("kind") or t.get("taxonomy") or "")
                slug = str(t.get("slug") or "")
                name = str(t.get("name") or slug)
                if kind in (TagKind.GENRE, TagKind.MOOD, TagKind.STATION_TAG) and slug:
                    tags.append((slug, name, kind))
        return tags

    for kind in (TagKind.GENRE, TagKind.MOOD, TagKind.STATION_TAG):
        entries = item.get(kind) or item.get(f"{kind}s") or []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    slug = str(entry.get("slug") or "")
                    name = str(entry.get("name") or slug)
                else:
                    slug = slugify(str(entry))
                    name = str(entry)
                if slug:
                    tags.append((slug, name, kind))
    return tags


def _parse_stream_count(item: dict[str, Any]) -> int:
    raw = (
        item.get("stream_count")
        or item.get("streams")
        or item.get("post-count-all")
        or item.get("post_count_all")
    )
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = str(url).strip()
    if not url or "dl.moziketo.ir" in url:
        return None
    return url


async def _upsert_tag(session: AsyncSession, slug: str, name: str, kind: str) -> Tag:
    tag = await session.scalar(select(Tag).where(Tag.slug == slug, Tag.kind == kind))
    if tag is None:
        tag = Tag(slug=slug, name=name, kind=kind)
        session.add(tag)
        await session.flush()
    else:
        tag.name = name
    return tag


async def _sync_track_tags(
    session: AsyncSession, track: Track, tags: list[tuple[str, str, str]]
) -> int:
    tag_objects: list[Tag] = []
    for slug, name, kind in tags:
        tag_objects.append(await _upsert_tag(session, slug, name, kind))
    track.tags = tag_objects
    return len(tag_objects)


async def import_catalog_payload(
    session: AsyncSession, payload: dict[str, Any] | list[Any]
) -> ImportResult:
    result = ImportResult()

    if isinstance(payload, list):
        tracks_data = payload
        artists_data: list[dict] = []
        playlists_data: list[dict] = []
    elif isinstance(payload, dict):
        tracks_data = payload.get("tracks") or []
        artists_data = payload.get("artists") or []
        playlists_data = payload.get("playlists") or []
    else:
        result.errors.append("Invalid JSON root — expected array or object")
        return result

    artist_meta: dict[str, dict] = {}
    for row in artists_data:
        slug = row.get("slug") or slugify(str(row.get("name") or ""))
        if slug:
            artist_meta[slug] = row

    for item in tracks_data:
        slug = item.get("slug") or ""
        audio = _clean_url(item.get("audio_url"))
        if not slug or not audio:
            result.skipped += 1
            continue

        title = html.unescape(str(item.get("title") or slug))
        artist_name = html.unescape(str(item.get("artist") or title))
        artist_slug = slugify(artist_name)

        meta = artist_meta.get(artist_slug, {})
        artist = await session.scalar(select(Artist).where(Artist.slug == artist_slug))
        if artist is None:
            artist = Artist(
                slug=artist_slug,
                name=artist_name,
                name_en=artist_slug,
                bio=meta.get("bio"),
                cover_url=_clean_url(meta.get("cover_url")),
            )
            session.add(artist)
            await session.flush()
            result.artists_upserted += 1
        else:
            bio = meta.get("bio") or item.get("artist_bio")
            cover = _clean_url(meta.get("cover_url") or item.get("artist_cover_url"))
            if bio:
                artist.bio = bio
            if cover:
                artist.cover_url = cover

        published_at = datetime.now(UTC)
        pub_raw = item.get("published_at")
        if pub_raw:
            try:
                published_at = datetime.fromisoformat(str(pub_raw).replace(" ", "T")).replace(
                    tzinfo=UTC
                )
            except ValueError:
                pass

        cover = _clean_url(item.get("cover_url"))
        duration = item.get("duration_seconds")
        if duration is not None:
            try:
                duration = int(duration)
            except (TypeError, ValueError):
                duration = None

        stream_count = _parse_stream_count(item)
        description = item.get("description") or item.get("editor_note")

        track = await session.scalar(select(Track).where(Track.slug == slug))
        if track is None:
            track = Track(
                slug=slug,
                title=title,
                artist_id=artist.id,
                audio_url=audio,
                cover_url=cover,
                duration_seconds=duration,
                published_at=published_at,
                stream_count=stream_count,
                description=str(description) if description else None,
            )
            session.add(track)
            await session.flush()
            result.tracks_upserted += 1
        else:
            track.title = title
            track.artist_id = artist.id
            track.audio_url = audio
            if cover:
                track.cover_url = cover
            if duration is not None:
                track.duration_seconds = duration
            if track.published_at is None:
                track.published_at = published_at
            if stream_count > 0:
                track.stream_count = stream_count
            if description:
                track.description = str(description)
            result.tracks_upserted += 1

        tags = _parse_tags(item)
        if tags:
            result.tags_upserted += await _sync_track_tags(session, track, tags)

    for pl_item in playlists_data:
        pl_slug = pl_item.get("slug") or ""
        if not pl_slug:
            result.skipped += 1
            continue

        title = html.unescape(str(pl_item.get("title") or pl_slug))
        cover = _clean_url(pl_item.get("cover_url"))
        description = pl_item.get("description")
        track_slugs = pl_item.get("track_slugs") or pl_item.get("playlist_tracks") or []

        published_at = datetime.now(UTC)
        pub_raw = pl_item.get("published_at")
        if pub_raw:
            try:
                published_at = datetime.fromisoformat(str(pub_raw).replace(" ", "T")).replace(
                    tzinfo=UTC
                )
            except ValueError:
                pass

        playlist = await session.scalar(select(Playlist).where(Playlist.slug == pl_slug))
        if playlist is None:
            playlist = Playlist(
                slug=pl_slug,
                title=title,
                cover_url=cover,
                description=str(description) if description else None,
                kind=PlaylistKind.EDITORIAL,
                published_at=published_at,
            )
            session.add(playlist)
            await session.flush()
            result.playlists_upserted += 1
        else:
            playlist.title = title
            if cover:
                playlist.cover_url = cover
            if description:
                playlist.description = str(description)
            playlist.published_at = published_at or playlist.published_at

        await session.execute(
            delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id)
        )
        for position, track_slug in enumerate(track_slugs):
            track = await session.scalar(select(Track).where(Track.slug == track_slug))
            if track is None:
                continue
            session.add(
                PlaylistTrack(
                    playlist_id=playlist.id,
                    track_id=track.id,
                    position=position,
                )
            )

    await session.commit()
    await cache_delete_pattern("tracks:*")
    await cache_delete_pattern("albums:*")
    await cache_delete_pattern("browse:*")
    await cache_delete_pattern("tags:*")
    await cache_delete_pattern("playlists:*")
    await cache_delete_pattern("artists:*")

    return result
