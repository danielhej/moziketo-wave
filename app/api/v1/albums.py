from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.album import AlbumDetail, AlbumListResponse
from app.services import albums as albums_service

router = APIRouter(tags=["catalog"])


@router.get("/albums", response_model=AlbumListResponse, summary="List albums")
async def list_albums(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
) -> AlbumListResponse:
    return await albums_service.list_albums(session, page=page, page_size=page_size)


@router.get(
    "/albums/{slug}",
    response_model=AlbumDetail,
    summary="Get album by slug",
    responses={404: {"description": "Album not found"}},
)
async def get_album(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> AlbumDetail:
    return await albums_service.get_album(session, slug)
