from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.schemas.downloader import DownloaderIngestResponse


@pytest.fixture(autouse=True)
def _configure_downloader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOWNLOADER_URL", "http://downloader.test")
    monkeypatch.setenv("DOWNLOADER_SECRET", "test-secret")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ingest_download_proxies_to_downloader(client: AsyncClient) -> None:
    mock_response = DownloaderIngestResponse(
        download_url="https://dl.moziketo.ir/music/test.mp3",
        s3_key="music/test.mp3",
        size_bytes=1234,
        spotify_track_id="abc123",
    )
    with patch(
        "app.api.v1.admin.downloader.ingest_spotify",
        new=AsyncMock(return_value=mock_response),
    ):
        response = await client.post(
            "/api/v1/admin/ingest/download",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "spotify_url": "https://open.spotify.com/track/abc123",
                "key": "test.mp3",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["download_url"] == "https://dl.moziketo.ir/music/test.mp3"
    assert body["s3_key"] == "music/test.mp3"


@pytest.mark.asyncio
async def test_ingest_download_requires_admin_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/ingest/download",
        json={"spotify_url": "https://open.spotify.com/track/abc123"},
    )
    assert response.status_code == 403
