from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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
from app.schemas.admin_ops import (
    AdminCatalogSummary,
    AdminUserPatch,
    AdminUsersResponse,
    ImportStatusResponse,
)
from app.schemas.jobs import ImportQueuedResponse, JobResponse
from app.services import admin_catalog, admin_ops, import_catalog, import_wp, jobs

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


@router.get(
    "/catalog/summary",
    response_model=AdminCatalogSummary,
    dependencies=[Depends(_verify_admin_key)],
)
async def catalog_summary(session: AsyncSession = Depends(get_db_session)) -> AdminCatalogSummary:
    return await admin_ops.catalog_summary(session)


@router.get(
    "/import/status",
    response_model=ImportStatusResponse,
    dependencies=[Depends(_verify_admin_key)],
)
async def import_status(session: AsyncSession = Depends(get_db_session)) -> ImportStatusResponse:
    job = await admin_ops.latest_import_job(session)
    if job is None:
        return ImportStatusResponse()
    return ImportStatusResponse(
        last_job_id=str(job.id),
        status=job.status,
        created_at=job.created_at,
        finished_at=job.finished_at,
        result=job.result_json,
        error=job.error,
    )


@router.get(
    "/users",
    response_model=AdminUsersResponse,
    dependencies=[Depends(_verify_admin_key)],
)
async def list_users(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> AdminUsersResponse:
    return await admin_ops.list_users(session, page=page, page_size=page_size)


@router.patch(
    "/users/{user_id}",
    dependencies=[Depends(_verify_admin_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_user(
    user_id: UUID,
    payload: AdminUserPatch,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await admin_ops.set_user_active(session, user_id, active=payload.is_active)


@router.post(
    "/import",
    response_model=ImportQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_admin_key)],
)
async def trigger_import(
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100,
) -> ImportQueuedResponse:
    job_id = await jobs.enqueue_import(session, limit=limit)
    return ImportQueuedResponse(job_id=str(job_id))


@router.post(
    "/import/sync",
    response_model=ImportResult,
    dependencies=[Depends(_verify_admin_key)],
    summary="Synchronous WP import (legacy)",
)
async def trigger_import_sync(
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100,
) -> ImportResult:
    return await import_wp.run_import(session, limit=limit)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(_verify_admin_key)],
)
async def get_job(job_id: UUID, session: AsyncSession = Depends(get_db_session)) -> JobResponse:
    data = await jobs.get_job_response(session, job_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse(**data)


@router.post(
    "/reindex",
    response_model=ImportQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_admin_key)],
)
async def trigger_reindex(session: AsyncSession = Depends(get_db_session)) -> ImportQueuedResponse:
    job_id = await jobs.enqueue_reindex(session)
    return ImportQueuedResponse(job_id=str(job_id))


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
