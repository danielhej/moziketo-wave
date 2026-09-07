from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Playlist, PlaylistKind, PlaylistTrack, Track, User
from app.schemas import (
    CreatePlaylistRequest,
    PlaylistDetail,
    PlaylistListResponse,
    PlaylistSummary,
    UpdatePlaylistRequest,
)
from app.services.cache import cache_delete_pattern, cache_get, cache_set
from app.services.catalog import _track_summary
from app.services.media import published_track_filter


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "playlist"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base[:180]
    suffix = 1
    while await session.scalar(select(Playlist.id).where(Playlist.slug == slug)):
        slug = f"{base[:170]}-{suffix}"
        suffix += 1
    return slug


def _playlist_summary(playlist: Playlist, track_count: int) -> PlaylistSummary:
    return PlaylistSummary(
        id=str(playlist.id),
        slug=playlist.slug,
        title=playlist.title,
        cover_url=playlist.cover_url,
        description=playlist.description,
        kind=playlist.kind,
        track_count=track_count,
    )


async def _playlist_tracks(session: AsyncSession, playlist: Playlist) -> list[Track]:
    result = await session.execute(
        select(Track)
        .join(PlaylistTrack, PlaylistTrack.track_id == Track.id)
        .options(selectinload(Track.artist))
        .where(PlaylistTrack.playlist_id == playlist.id)
        .where(published_track_filter())
        .order_by(PlaylistTrack.position)
    )
    return list(result.scalars().unique().all())


async def list_editorial_playlists(session: AsyncSession) -> PlaylistListResponse:
    cache_key = "playlists:editorial:list"
    cached = await cache_get(cache_key)
    if cached is not None:
        return PlaylistListResponse.model_validate(cached)

    result = await session.execute(
        select(Playlist)
        .where(Playlist.kind == PlaylistKind.EDITORIAL)
        .where(Playlist.published_at.isnot(None))
        .order_by(Playlist.title)
    )
    playlists = result.scalars().all()

    items: list[PlaylistSummary] = []
    for pl in playlists:
        count = (
            await session.scalar(
                select(func.count())
                .select_from(PlaylistTrack)
                .join(Track, PlaylistTrack.track_id == Track.id)
                .where(PlaylistTrack.playlist_id == pl.id)
                .where(published_track_filter())
            )
            or 0
        )
        items.append(_playlist_summary(pl, count))

    response = PlaylistListResponse(items=items, total=len(items))
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def get_editorial_playlist(session: AsyncSession, slug: str) -> PlaylistDetail:
    cache_key = f"playlists:editorial:{slug}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return PlaylistDetail.model_validate(cached)

    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.slug == slug,
            Playlist.kind == PlaylistKind.EDITORIAL,
            Playlist.published_at.isnot(None),
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    tracks = await _playlist_tracks(session, playlist)
    response = PlaylistDetail(
        id=str(playlist.id),
        slug=playlist.slug,
        title=playlist.title,
        cover_url=playlist.cover_url,
        description=playlist.description,
        kind=playlist.kind,
        track_count=len(tracks),
        tracks=[_track_summary(t) for t in tracks],
        published_at=playlist.published_at,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def _resolve_track_slugs(
    session: AsyncSession, slugs: list[str]
) -> list[Track]:
    if not slugs:
        return []
    result = await session.execute(
        select(Track)
        .options(selectinload(Track.artist))
        .where(Track.slug.in_(slugs))
        .where(published_track_filter())
    )
    found = {t.slug: t for t in result.scalars().unique().all()}
    missing = [s for s in slugs if s not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tracks not found: {', '.join(missing)}",
        )
    return [found[s] for s in slugs]


async def _set_playlist_tracks(
    session: AsyncSession, playlist: Playlist, tracks: list[Track]
) -> None:
    await session.execute(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id))
    for position, track in enumerate(tracks):
        session.add(
            PlaylistTrack(playlist_id=playlist.id, track_id=track.id, position=position)
        )


async def list_user_playlists(session: AsyncSession, user: User) -> PlaylistListResponse:
    result = await session.execute(
        select(Playlist)
        .where(Playlist.kind == PlaylistKind.USER, Playlist.user_id == user.id)
        .order_by(Playlist.created_at.desc())
    )
    playlists = result.scalars().all()
    items: list[PlaylistSummary] = []
    for pl in playlists:
        count = await session.scalar(
            select(func.count()).select_from(PlaylistTrack).where(
                PlaylistTrack.playlist_id == pl.id
            )
        ) or 0
        items.append(_playlist_summary(pl, int(count)))
    return PlaylistListResponse(items=items, total=len(items))


async def create_user_playlist(
    session: AsyncSession, user: User, payload: CreatePlaylistRequest
) -> PlaylistDetail:
    base_slug = await _unique_slug(session, _slugify(payload.title))
    playlist = Playlist(
        slug=base_slug,
        title=payload.title,
        kind=PlaylistKind.USER,
        user_id=user.id,
    )
    session.add(playlist)
    await session.flush()

    tracks = await _resolve_track_slugs(session, payload.track_slugs)
    if tracks:
        await _set_playlist_tracks(session, playlist, tracks)

    await session.commit()
    await session.refresh(playlist)
    return await get_user_playlist(session, user, playlist.id)


async def get_user_playlist(
    session: AsyncSession, user: User, playlist_id: uuid.UUID
) -> PlaylistDetail:
    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.kind == PlaylistKind.USER,
            Playlist.user_id == user.id,
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    tracks = await _playlist_tracks(session, playlist)
    return PlaylistDetail(
        id=str(playlist.id),
        slug=playlist.slug,
        title=playlist.title,
        cover_url=playlist.cover_url,
        description=playlist.description,
        kind=playlist.kind,
        track_count=len(tracks),
        tracks=[_track_summary(t) for t in tracks],
        published_at=playlist.published_at,
    )


async def update_user_playlist(
    session: AsyncSession,
    user: User,
    playlist_id: uuid.UUID,
    payload: UpdatePlaylistRequest,
) -> PlaylistDetail:
    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.kind == PlaylistKind.USER,
            Playlist.user_id == user.id,
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    if payload.title is not None:
        playlist.title = payload.title
    if payload.track_slugs is not None:
        tracks = await _resolve_track_slugs(session, payload.track_slugs)
        await _set_playlist_tracks(session, playlist, tracks)

    await session.commit()
    return await get_user_playlist(session, user, playlist_id)


async def delete_user_playlist(
    session: AsyncSession, user: User, playlist_id: uuid.UUID
) -> None:
    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.kind == PlaylistKind.USER,
            Playlist.user_id == user.id,
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    await session.delete(playlist)
    await session.commit()


async def add_track_to_user_playlist(
    session: AsyncSession, user: User, playlist_id: uuid.UUID, track_slug: str
) -> PlaylistDetail:
    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.kind == PlaylistKind.USER,
            Playlist.user_id == user.id,
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    track = await session.scalar(
        select(Track).where(Track.slug == track_slug).where(published_track_filter())
    )
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    existing = await session.scalar(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track.id,
        )
    )
    if existing is None:
        max_pos = await session.scalar(
            select(func.max(PlaylistTrack.position)).where(
                PlaylistTrack.playlist_id == playlist.id
            )
        )
        session.add(
            PlaylistTrack(
                playlist_id=playlist.id,
                track_id=track.id,
                position=(max_pos or -1) + 1,
            )
        )
        await session.commit()

    return await get_user_playlist(session, user, playlist_id)


async def remove_track_from_user_playlist(
    session: AsyncSession, user: User, playlist_id: uuid.UUID, track_slug: str
) -> PlaylistDetail:
    playlist = await session.scalar(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.kind == PlaylistKind.USER,
            Playlist.user_id == user.id,
        )
    )
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")

    track = await session.scalar(select(Track).where(Track.slug == track_slug))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    pt = await session.scalar(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track.id,
        )
    )
    if pt is not None:
        await session.delete(pt)
        await session.commit()

    return await get_user_playlist(session, user, playlist_id)


async def invalidate_playlist_cache() -> None:
    await cache_delete_pattern("playlists:*")
