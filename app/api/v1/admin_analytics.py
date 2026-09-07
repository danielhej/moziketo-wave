from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.v1.admin import _verify_admin_key
from app.schemas.admin_analytics import (
    AnalyticsOverview,
    TimeSeriesResponse,
    TopArtistsResponse,
    TopTracksResponse,
)
from app.services import admin_analytics

router = APIRouter(
    prefix="/admin/analytics",
    tags=["admin"],
    dependencies=[Depends(_verify_admin_key)],
)


def _bad_period(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsOverview:
    return await admin_analytics.get_overview(session)


@router.get("/top-tracks", response_model=TopTracksResponse)
async def analytics_top_tracks(
    period: Annotated[str, Query(description="e.g. 7d, 30d")] = "7d",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    session: AsyncSession = Depends(get_db_session),
) -> TopTracksResponse:
    try:
        return await admin_analytics.get_top_tracks(session, period=period, limit=limit)
    except ValueError as exc:
        raise _bad_period(exc) from exc


@router.get("/top-artists", response_model=TopArtistsResponse)
async def analytics_top_artists(
    period: Annotated[str, Query(description="e.g. 7d, 30d")] = "7d",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    session: AsyncSession = Depends(get_db_session),
) -> TopArtistsResponse:
    try:
        return await admin_analytics.get_top_artists(session, period=period, limit=limit)
    except ValueError as exc:
        raise _bad_period(exc) from exc


@router.get("/signups", response_model=TimeSeriesResponse)
async def analytics_signups(
    period: Annotated[str, Query(description="e.g. 30d")] = "30d",
    session: AsyncSession = Depends(get_db_session),
) -> TimeSeriesResponse:
    try:
        return await admin_analytics.get_signups_series(session, period=period)
    except ValueError as exc:
        raise _bad_period(exc) from exc


@router.get("/plays", response_model=TimeSeriesResponse)
async def analytics_plays(
    period: Annotated[str, Query(description="e.g. 30d")] = "30d",
    session: AsyncSession = Depends(get_db_session),
) -> TimeSeriesResponse:
    try:
        return await admin_analytics.get_plays_series(session, period=period)
    except ValueError as exc:
        raise _bad_period(exc) from exc
