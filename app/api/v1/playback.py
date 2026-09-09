from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, rate_limit_playback
from app.services import catalog as catalog_service
from app.services import stream_key
from app.services.audio_proxy import proxy_audio

router = APIRouter(tags=["playback"])


@router.post(
    "/warm/{key}",
    summary="Prefetch stream before play click",
    description=(
        "Call when a track row is visible (before play). "
        "Returns ready when CDN URL is cached — then play is under 2s."
    ),
)
async def warm_track(
    key: str,
    title: Annotated[str | None, Query()] = None,
    artist: Annotated[str | None, Query()] = None,
    _: None = Depends(rate_limit_playback),
) -> dict:
    return await stream_key.warm_track(key, title=title, artist=artist)


@router.get(
    "/stream/{key}",
    response_model=None,
    summary="Stream by key",
    description=(
        "Catalog slug or Spotify track id. Proxied audio with Range support "
        "for HTML5 audio (no redirect to storage)."
    ),
    responses={
        200: {"description": "Full MP3 stream"},
        206: {"description": "Partial content (Range request)"},
    },
)
async def stream_by_key(
    key: str,
    request: Request,
    title: Annotated[str | None, Query(description="Skip metadata lookup")] = None,
    artist: Annotated[str | None, Query(description="Skip metadata lookup")] = None,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit_playback),
) -> StreamingResponse:
    return await stream_key.resolve_stream(
        session,
        key,
        range_header=request.headers.get("range"),
        title_hint=title,
        artist_hint=artist,
    )


@router.get("/tracks/{slug}/stream")
async def stream_track(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit_playback),
) -> StreamingResponse:
    url = await catalog_service.resolve_stream_url(session, slug)
    return await proxy_audio(url, range_header=request.headers.get("range"), filename=f"{slug}.mp3")


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
