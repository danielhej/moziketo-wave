import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import User
from app.schemas import (
    CreatePlaylistRequest,
    PlaylistDetail,
    PlaylistListResponse,
    UpdatePlaylistRequest,
)
from app.services import playlists as playlists_service

router = APIRouter(tags=["playlists"])
me_router = APIRouter(prefix="/me/playlists", tags=["playlists"])


@router.get(
    "/playlists",
    response_model=PlaylistListResponse,
    summary="List editorial playlists",
)
async def list_playlists(
    session: AsyncSession = Depends(get_db_session),
) -> PlaylistListResponse:
    return await playlists_service.list_editorial_playlists(session)


@router.get(
    "/playlists/{slug}",
    response_model=PlaylistDetail,
    summary="Get editorial playlist",
)
async def get_playlist(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> PlaylistDetail:
    return await playlists_service.get_editorial_playlist(session, slug)


@me_router.get("", response_model=PlaylistListResponse)
async def list_my_playlists(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistListResponse:
    return await playlists_service.list_user_playlists(session, user)


@me_router.post("", response_model=PlaylistDetail, status_code=201)
async def create_my_playlist(
    payload: CreatePlaylistRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistDetail:
    return await playlists_service.create_user_playlist(session, user, payload)


@me_router.get("/{playlist_id}", response_model=PlaylistDetail)
async def get_my_playlist(
    playlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistDetail:
    return await playlists_service.get_user_playlist(session, user, playlist_id)


@me_router.patch("/{playlist_id}", response_model=PlaylistDetail)
async def update_my_playlist(
    playlist_id: uuid.UUID,
    payload: UpdatePlaylistRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistDetail:
    return await playlists_service.update_user_playlist(
        session, user, playlist_id, payload
    )


@me_router.delete("/{playlist_id}", status_code=204)
async def delete_my_playlist(
    playlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await playlists_service.delete_user_playlist(session, user, playlist_id)


@me_router.post("/{playlist_id}/tracks/{track_slug}", response_model=PlaylistDetail)
async def add_track_to_my_playlist(
    playlist_id: uuid.UUID,
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistDetail:
    return await playlists_service.add_track_to_user_playlist(
        session, user, playlist_id, track_slug
    )


@me_router.delete("/{playlist_id}/tracks/{track_slug}", response_model=PlaylistDetail)
async def remove_track_from_my_playlist(
    playlist_id: uuid.UUID,
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> PlaylistDetail:
    return await playlists_service.remove_track_from_user_playlist(
        session, user, playlist_id, track_slug
    )
