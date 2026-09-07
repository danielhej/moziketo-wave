from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import User
from app.schemas.browse import BrowseResponse
from app.schemas.catalog import TrackListResponse, TrackSummary
from app.services import recommendations as recommendations_service

router = APIRouter(prefix="/me", tags=["recommendations"])
catalog_router = APIRouter(tags=["recommendations"])


@router.get(
    "/recommendations",
    response_model=BrowseResponse,
    summary="Personalized track recommendations",
)
async def my_recommendations(
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BrowseResponse:
    return await recommendations_service.get_user_recommendations(session, user, limit=limit)


@catalog_router.get(
    "/tracks/{slug}/similar",
    response_model=TrackListResponse,
    summary="Similar tracks",
)
async def similar_tracks(
    slug: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    session: AsyncSession = Depends(get_db_session),
) -> TrackListResponse:
    items: list[TrackSummary] = await recommendations_service.get_similar_tracks(
        session, slug, limit=limit
    )
    return TrackListResponse(items=items, total=len(items), page=1, page_size=limit)
