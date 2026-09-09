from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, rate_limit_playback
from app.services import catalog as catalog_service
from app.services import stream_key

router = APIRouter(tags=["playback"])


@router.get(
    "/stream/{key}",
    response_model=None,
    summary="Stream by key",
    description=(
        "Catalog slug or Spotify track id. DB hit redirects to S3; "
        "miss proxies live stream via moz-downloader."
    ),
    responses={
        302: {"description": "Redirect to catalog audio (S3 presigned URL)"},
        200: {"description": "Proxied MP3 stream while ingest runs"},
    },
)
async def stream_by_key(
    key: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit_playback),
) -> RedirectResponse | StreamingResponse:
    return await stream_key.resolve_stream(session, key)


@router.get("/tracks/{slug}/stream")
async def stream_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit_playback),
) -> RedirectResponse:
    url = await catalog_service.resolve_stream_url(session, slug)
    return RedirectResponse(url=url, status_code=302)


@router.get("/tracks/{slug}/download")
async def download_track(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit_playback),
) -> RedirectResponse:
    url = await catalog_service.resolve_stream_url(session, slug)
    filename = quote(f"{slug}.mp3")
    return RedirectResponse(
        url=url,
        status_code=302,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
