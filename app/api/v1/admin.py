from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import get_settings
from app.schemas.admin import ImportResult
from app.services import import_catalog, import_wp

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


@router.post("/import", response_model=ImportResult, dependencies=[Depends(_verify_admin_key)])
async def trigger_import(
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100,
) -> ImportResult:
    return await import_wp.run_import(session, limit=limit)


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
