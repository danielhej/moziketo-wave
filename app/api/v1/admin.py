from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import get_settings
from app.schemas.admin import ImportResult
from app.schemas.admin_catalog import (
    AdminAlbumCreate,
    AdminAlbumPatch,
    AdminArtistPatch,
    AdminPlaylistPatch,
    AdminTrackPatch,
)
from app.services import admin_catalog, import_catalog, import_wp

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


@router.post("/import", response_model=ImportResult, dependencies=[Depends(_verify_admin_key)])
async def trigger_import(
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100,
) -> ImportResult:
    return await import_wp.run_import(session, limit=limit)


@router.post(
    "/import-json",
    response_model=ImportResult,
    dependencies=[Depends(_verify_admin_key)],
    summary="Import catalog from WP JSON export body",
)
async def trigger_json_import(
    payload: dict[str, Any] | list[Any],
    session: AsyncSession = Depends(get_db_session),
) -> ImportResult:
    return await import_catalog.import_catalog_payload(session, payload)


@router.patch(
    "/tracks/{slug}",
    dependencies=[Depends(_verify_admin_key)],
    summary="Patch track metadata or publish state",
)
async def patch_track(
    slug: str,
    payload: AdminTrackPatch,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    track = await admin_catalog.patch_track(session, slug, payload)
    return {"slug": track.slug, "title": track.title}


@router.post(
    "/tracks/{slug}/publish",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def publish_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await admin_catalog.publish_track(session, slug)


@router.post(
    "/tracks/{slug}/unpublish",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unpublish_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await admin_catalog.unpublish_track(session, slug)


@router.patch(
    "/artists/{slug}",
    dependencies=[Depends(_verify_admin_key)],
    summary="Patch artist metadata",
)
async def patch_artist(
    slug: str,
    payload: AdminArtistPatch,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    artist = await admin_catalog.patch_artist(session, slug, payload)
    return {"slug": artist.slug, "name": artist.name}


@router.patch(
    "/playlists/{slug}",
    dependencies=[Depends(_verify_admin_key)],
    summary="Patch editorial playlist",
)
async def patch_playlist(
    slug: str,
    payload: AdminPlaylistPatch,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    playlist = await admin_catalog.patch_playlist(session, slug, payload)
    return {"slug": playlist.slug, "title": playlist.title}


@router.post(
    "/albums",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_201_CREATED,
    summary="Create album",
)
async def create_album(
    payload: AdminAlbumCreate,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    album = await admin_catalog.create_album(session, payload)
    return {"slug": album.slug, "title": album.title}


@router.patch(
    "/albums/{slug}",
    dependencies=[Depends(_verify_admin_key)],
    summary="Patch album metadata or track list",
)
async def patch_album(
    slug: str,
    payload: AdminAlbumPatch,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    album = await admin_catalog.patch_album(session, slug, payload)
    return {"slug": album.slug, "title": album.title}


@router.post(
    "/albums/{slug}/publish",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def publish_album(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await admin_catalog.publish_album(session, slug)


@router.post(
    "/albums/{slug}/unpublish",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unpublish_album(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await admin_catalog.unpublish_album(session, slug)
