
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas import BrowseResponse
from app.services import browse as browse_service

router = APIRouter(tags=["catalog"])


@router.get(
    "/browse",
    response_model=BrowseResponse,
    summary="Browse home sections",
    description="Popular, latest, and new release track sections for the home screen.",
)
async def browse_home(
    session: AsyncSession = Depends(get_db_session),
) -> BrowseResponse:
    return await browse_service.get_browse(session)
