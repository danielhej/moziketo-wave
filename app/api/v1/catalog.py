from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas import (
    ArtistDetail,
    ArtistListResponse,
    HealthResponse,
    SearchResponse,
    TrackDetail,
    TrackListResponse,
)
from app.services import catalog as catalog_service

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check",
    description="Returns service status and PostgreSQL connectivity.",
)
async def health(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    db_ok = await catalog_service.check_database(session)
    return HealthResponse(database="ok" if db_ok else "error")


@router.get(
    "/tracks",
    response_model=TrackListResponse,
    tags=["catalog"],
    summary="List tracks",
    description="Paginated catalog of published tracks, newest first.",
)
async def list_tracks(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> TrackListResponse:
    return await catalog_service.list_tracks(session, page=page, page_size=page_size)


@router.get(
    "/tracks/{slug}",
    response_model=TrackDetail,
    tags=["catalog"],
    summary="Get track by slug",
    responses={404: {"description": "Track not found"}},
)
async def get_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> TrackDetail:
    return await catalog_service.get_track(session, slug)


@router.get(
    "/artists",
    response_model=ArtistListResponse,
    tags=["catalog"],
    summary="List artists",
    description="Paginated list of artists with track counts.",
)
async def list_artists(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistListResponse:
    return await catalog_service.list_artists(session, page=page, page_size=page_size)


@router.get(
    "/artists/{slug}",
    response_model=ArtistDetail,
    tags=["catalog"],
    summary="Get artist by slug",
    responses={404: {"description": "Artist not found"}},
)
async def get_artist(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistDetail:
    return await catalog_service.get_artist(session, slug)


@router.get(
    "/search",
    response_model=SearchResponse,
    tags=["catalog"],
    summary="Search catalog",
    description="Search tracks and artists by title, name, or slug (case-insensitive).",
)
async def search_catalog(
    q: Annotated[str, Query(min_length=2, description="Search term (min 2 chars)")],
    limit: Annotated[int, Query(ge=1, le=50, description="Max results per type")] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    return await catalog_service.search_catalog(session, q=q, limit=limit)
