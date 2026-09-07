from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artist, Playlist, PlaylistKind, PlaylistTrack, Track
from app.schemas.admin_catalog import AdminArtistPatch, AdminPlaylistPatch, AdminTrackPatch
from app.services.cache import cache_delete_pattern


async def _invalidate_catalog_cache() -> None:
    await cache_delete_pattern("catalog:*")


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
    return track


async def publish_track(session: AsyncSession, slug: str) -> Track:
    return await patch_track(
        session,
        slug,
        AdminTrackPatch(published_at=datetime.now(UTC)),
    )


async def unpublish_track(session: AsyncSession, slug: str) -> Track:
    return await patch_track(session, slug, AdminTrackPatch(published_at=None))


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
