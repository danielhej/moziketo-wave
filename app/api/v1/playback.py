from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.services import catalog as catalog_service

router = APIRouter(tags=["playback"])


@router.get("/tracks/{slug}/stream")
async def stream_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    url = await catalog_service.resolve_stream_url(session, slug)
    return RedirectResponse(url=url, status_code=302)


@router.get("/tracks/{slug}/download")
async def download_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    url = await catalog_service.resolve_stream_url(session, slug)
    filename = quote(f"{slug}.mp3")
    return RedirectResponse(
        url=url,
        status_code=302,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
