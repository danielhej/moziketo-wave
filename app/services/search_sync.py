from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, Artist, Track
from app.services.admin_ops import build_track_doc
from app.services.search_meili import delete_document, meili_available, upsert_documents

logger = logging.getLogger(__name__)


async def sync_track(session: AsyncSession, track: Track) -> None:
    if not meili_available():
        return
    try:
        if track.published_at is None:
            await delete_document("tracks", str(track.id))
            return
        doc = await build_track_doc(session, track)
        await upsert_documents("tracks", [doc])
    except Exception:
        logger.exception("Meili sync failed for track %s", track.slug)


async def sync_artist(session: AsyncSession, artist: Artist) -> None:
    if not meili_available():
        return
    try:
        doc = {
            "id": str(artist.id),
            "slug": artist.slug,
            "name": artist.name,
            "name_en": artist.name_en,
            "cover_url": artist.cover_url,
            "track_count": 0,
        }
        await upsert_documents("artists", [doc])
    except Exception:
        logger.exception("Meili sync failed for artist %s", artist.slug)


async def sync_album(session: AsyncSession, album: Album) -> None:
    if not meili_available():
        return
    try:
        if album.published_at is None:
            await delete_document("albums", str(album.id))
            return
        await session.refresh(album, ["artist"])
        doc = {
            "id": str(album.id),
            "slug": album.slug,
            "title": album.title,
            "artist_name": album.artist.name if album.artist else "",
            "published": True,
        }
        await upsert_documents("albums", [doc])
    except Exception:
        logger.exception("Meili sync failed for album %s", album.slug)
