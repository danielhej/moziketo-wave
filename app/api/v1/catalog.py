from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas import (
    ArtistDetail,
    ArtistListResponse,
    HealthResponse,
    TrackDetail,
    TrackListResponse,
)
from app.services import catalog as catalog_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    db_ok = await catalog_service.check_database(session)
    return HealthResponse(database="ok" if db_ok else "error")


@router.get("/tracks", response_model=TrackListResponse, tags=["catalog"])
async def list_tracks(
    page: int = 1,
    page_size: int = 24,
    session: AsyncSession = Depends(get_db_session),
) -> TrackListResponse:
    return await catalog_service.list_tracks(session, page=page, page_size=page_size)


@router.get("/tracks/{slug}", response_model=TrackDetail, tags=["catalog"])
async def get_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> TrackDetail:
    return await catalog_service.get_track(session, slug)


@router.get("/artists", response_model=ArtistListResponse, tags=["catalog"])
async def list_artists(
    page: int = 1,
    page_size: int = 24,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistListResponse:
    return await catalog_service.list_artists(session, page=page, page_size=page_size)


@router.get("/artists/{slug}", response_model=ArtistDetail, tags=["catalog"])
async def get_artist(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistDetail:
    return await catalog_service.get_artist(session, slug)
