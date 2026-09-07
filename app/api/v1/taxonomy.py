from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas import TagListResponse, TagTrackListResponse
from app.services import tags as tags_service

router = APIRouter(tags=["catalog"])


@router.get("/genres", response_model=TagListResponse, summary="List genres")
async def list_genres(
    session: AsyncSession = Depends(get_db_session),
) -> TagListResponse:
    return await tags_service.list_tags_by_kind(session, "genre")


@router.get(
    "/genres/{slug}/tracks",
    response_model=TagTrackListResponse,
    summary="Tracks by genre",
)
async def list_genre_tracks(
    slug: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> TagTrackListResponse:
    return await tags_service.list_tracks_for_tag(
        session, kind="genre", slug=slug, page=page, page_size=page_size
    )


@router.get("/moods", response_model=TagListResponse, summary="List moods")
async def list_moods(
    session: AsyncSession = Depends(get_db_session),
) -> TagListResponse:
    return await tags_service.list_tags_by_kind(session, "mood")


@router.get(
    "/moods/{slug}/tracks",
    response_model=TagTrackListResponse,
    summary="Tracks by mood",
)
async def list_mood_tracks(
    slug: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> TagTrackListResponse:
    return await tags_service.list_tracks_for_tag(
        session, kind="mood", slug=slug, page=page, page_size=page_size
    )


@router.get(
    "/tags/{slug}/tracks",
    response_model=TagTrackListResponse,
    summary="Tracks by station tag",
)
async def list_tag_tracks(
    slug: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> TagTrackListResponse:
    return await tags_service.list_tracks_for_tag(
        session, kind="station_tag", slug=slug, page=page, page_size=page_size
    )
