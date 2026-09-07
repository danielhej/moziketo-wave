from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import User
from app.schemas.catalog import TrackListResponse
from app.services import history as history_service

router = APIRouter(prefix="/me", tags=["history"])


@router.post(
    "/plays/{track_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record a play event",
)
async def record_play(
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await history_service.record_play(session, user, track_slug)


@router.get(
    "/history/recent",
    response_model=TrackListResponse,
    summary="Recently played tracks (deduplicated)",
)
async def recent_history(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TrackListResponse:
    return await history_service.list_recent_history(session, user, limit=limit)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT, summary="Clear play history")
async def clear_history(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await history_service.clear_history(session, user)


@router.delete(
    "/history/{track_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a track from play history",
)
async def remove_from_history(
    track_slug: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await history_service.remove_track_from_history(session, user, track_slug)
