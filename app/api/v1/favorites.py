from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import User
from app.schemas import TrackListResponse, TrackSummary
from app.services import favorites as favorites_service

router = APIRouter(prefix="/me/favorites", tags=["favorites"])


@router.get("", response_model=TrackListResponse)
async def list_my_favorites(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TrackListResponse:
    return await favorites_service.list_favorites(
        session, user, page=page, page_size=page_size
    )


@router.post("/{track_slug}", response_model=TrackSummary, status_code=201)
async def add_my_favorite(
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TrackSummary:
    return await favorites_service.add_favorite(session, user, track_slug)


@router.delete("/{track_slug}", status_code=204)
async def remove_my_favorite(
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await favorites_service.remove_favorite(session, user, track_slug)
