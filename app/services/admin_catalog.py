from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Album, Artist, Playlist, PlaylistKind, PlaylistTrack, Track
from app.models.webhook import WebhookEvent
from app.schemas.admin_catalog import (
    AdminAlbumCreate,
    AdminAlbumPatch,
    AdminArtistPatch,
    AdminPlaylistPatch,
    AdminTrackPatch,
)
from app.services.cache import cache_delete_pattern
from app.services.search_sync import sync_album, sync_artist, sync_track
from app.services.webhooks import emit_event


async def _invalidate_catalog_cache() -> None:
    for pattern in ("tracks:*", "albums:*", "browse:*", "artists:*", "playlists:*", "tags:*"):
        await cache_delete_pattern(pattern)


async def patch_track(session: AsyncSession, slug: str, data: AdminTrackPatch) -> Track:
    track = await session.scalar(select(Track).where(Track.slug == slug))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(track, field, value)

    await session.commit()
    await session.refresh(track)
    await _invalidate_catalog_cache()
    await sync_track(session, track)
    return track


async def publish_track(session: AsyncSession, slug: str) -> Track:
    track = await patch_track(
        session,
        slug,
        AdminTrackPatch(published_at=datetime.now(UTC)),
    )
    await emit_event(session, WebhookEvent.TRACK_PUBLISHED, {"slug": slug})
    return track


async def unpublish_track(session: AsyncSession, slug: str) -> Track:
    track = await patch_track(session, slug, AdminTrackPatch(published_at=None))
    await emit_event(session, WebhookEvent.TRACK_UNPUBLISHED, {"slug": slug})
    return track


async def patch_artist(session: AsyncSession, slug: str, data: AdminArtistPatch) -> Artist:
    artist = await session.scalar(select(Artist).where(Artist.slug == slug))
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")

    if data.name is not None:
        artist.name = data.name
    if data.name_en is not None:
        artist.name_en = data.name_en
    if data.bio is not None:
        artist.bio = data.bio
    if data.cover_url is not None:
        artist.cover_url = data.cover_url

    await session.commit()
    await session.refresh(artist)
    await _invalidate_catalog_cache()
    await sync_artist(session, artist)
    return artist


async def patch_playlist(
    session: AsyncSession, slug: str, data: AdminPlaylistPatch
) -> Playlist:
    playlist = await session.scalar(select(Playlist).where(Playlist.slug == slug))
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    if playlist.kind != PlaylistKind.EDITORIAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only editorial playlists can be patched via admin",
        )

    if data.title is not None:
        playlist.title = data.title
    if data.description is not None:
        playlist.description = data.description
    if data.cover_url is not None:
        playlist.cover_url = data.cover_url
    if "published_at" in data.model_fields_set:
        playlist.published_at = data.published_at

    if data.track_slugs is not None:
        tracks: list[Track] = []
        for track_slug in data.track_slugs:
            track = await session.scalar(select(Track).where(Track.slug == track_slug))
            if track is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Track not found: {track_slug}",
                )
            tracks.append(track)

        await session.execute(
            delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id)
        )
        for position, track in enumerate(tracks):
            session.add(
                PlaylistTrack(playlist_id=playlist.id, track_id=track.id, position=position)
            )

    await session.commit()
    await session.refresh(playlist)
    await _invalidate_catalog_cache()
    return playlist


async def create_album(session: AsyncSession, data: AdminAlbumCreate) -> Album:
    artist = await session.scalar(select(Artist).where(Artist.slug == data.artist_slug))
    if artist is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Artist not found")

    existing = await session.scalar(select(Album).where(Album.slug == data.slug))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Album slug already exists",
        )

    album = Album(
        slug=data.slug,
        title=data.title,
        artist_id=artist.id,
        cover_url=data.cover_url,
        description=data.description,
        published_at=data.published_at,
    )
    session.add(album)
    await session.flush()

    if data.track_slugs:
        await _set_album_tracks(session, album, data.track_slugs)

    await session.commit()
    await session.refresh(album)
    await _invalidate_catalog_cache()
    if album.published_at is not None:
        await sync_album(session, album)
    return album


async def _set_album_tracks(session: AsyncSession, album: Album, track_slugs: list[str]) -> None:
    current = await session.scalars(select(Track).where(Track.album_id == album.id))
    for track in current:
        track.album_id = None

    for track_slug in track_slugs:
        track = await session.scalar(select(Track).where(Track.slug == track_slug))
        if track is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Track not found: {track_slug}",
            )
        track.album_id = album.id


async def patch_album(session: AsyncSession, slug: str, data: AdminAlbumPatch) -> Album:
    album = await session.scalar(
        select(Album).options(selectinload(Album.tracks)).where(Album.slug == slug)
    )
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    if data.title is not None:
        album.title = data.title
    if data.cover_url is not None:
        album.cover_url = data.cover_url
    if data.description is not None:
        album.description = data.description
    if "published_at" in data.model_fields_set:
        album.published_at = data.published_at

    if data.track_slugs is not None:
        await _set_album_tracks(session, album, data.track_slugs)

    await session.commit()
    await session.refresh(album)
    await _invalidate_catalog_cache()
    await sync_album(session, album)
    return album


async def publish_album(session: AsyncSession, slug: str) -> Album:
    album = await patch_album(
        session,
        slug,
        AdminAlbumPatch(published_at=datetime.now(UTC)),
    )
    await emit_event(session, WebhookEvent.ALBUM_PUBLISHED, {"slug": slug})
    return album


async def unpublish_album(session: AsyncSession, slug: str) -> Album:
    return await patch_album(session, slug, AdminAlbumPatch(published_at=None))
