from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.downloader import DownloaderIngestRequest, DownloaderIngestResponse


def downloader_configured() -> bool:
    settings = get_settings()
    return bool(settings.downloader_url.strip() and settings.downloader_secret.strip())


async def ingest_spotify(body: DownloaderIngestRequest) -> DownloaderIngestResponse:
    settings = get_settings()
    if not downloader_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Downloader service is not configured",
        )

    payload = {
        "url": str(body.spotify_url),
        "key": body.key,
        "title": body.title,
        "artist": body.artist,
    }
    headers = {"X-Moziketo-Relay-Secret": settings.downloader_secret}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            response = await client.post(
                f"{settings.downloader_url.rstrip('/')}/v1/ingest",
                json=payload,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Downloader unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        detail = response.text[:500]
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    return DownloaderIngestResponse.model_validate(response.json())
