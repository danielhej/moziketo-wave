"""Range-aware audio proxy — keeps CORS on wave origin for HTML5 audio."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

_AUDIO_HEADERS = ("content-range", "content-length", "accept-ranges")


async def proxy_audio(
    source_url: str,
    *,
    range_header: str | None = None,
    filename: str | None = None,
) -> StreamingResponse:
    """Stream audio from upstream (S3 or moz-downloader) with Range passthrough."""
    upstream_headers: dict[str, str] = {}
    if range_header:
        upstream_headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=15.0))
    try:
        request = client.build_request("GET", source_url, headers=upstream_headers)
        upstream = await client.send(request, stream=True)
    except httpx.RequestError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream stream unreachable: {exc}",
        ) from exc

    if upstream.status_code >= 400:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=body.decode(errors="replace")[:300],
        )

    response_headers: dict[str, str] = {
        "Accept-Ranges": upstream.headers.get("accept-ranges", "bytes"),
        "Cache-Control": upstream.headers.get("cache-control", "public, max-age=3600"),
    }
    for name in _AUDIO_HEADERS:
        value = upstream.headers.get(name)
        if value:
            response_headers[name.title()] = value

    if filename:
        response_headers["Content-Disposition"] = f'inline; filename="{filename}"'

    content_type = upstream.headers.get("content-type", "audio/mpeg")
    if "audio" not in content_type:
        content_type = "audio/mpeg"

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        body(),
        status_code=upstream.status_code,
        media_type=content_type,
        headers=response_headers,
    )
