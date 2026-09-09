from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.schemas.downloader import DownloaderPlayResponse
from app.services.spotify import SpotifyTrackHit


@pytest.fixture(autouse=True)
def _configure_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOWNLOADER_URL", "http://downloader.test")
    monkeypatch.setenv("DOWNLOADER_SECRET", "test-secret")
    get_settings.cache_clear()


async def test_stream_catalog_slug_redirect(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stream/bipolar", follow_redirects=False)
    assert response.status_code == 302
    assert "arvanstorage" in response.headers["location"]


async def test_stream_unknown_slug_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stream/not-a-spotify-id-slug", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_spotify_proxies_downloader(client: AsyncClient) -> None:
    spotify_key = "4uLU6hMCjMI75M1A2tKUQC"
    play = DownloaderPlayResponse(
        job_id="job-1",
        stream_url="http://downloader.test/v1/stream/job-1?token=t",
        status_url="http://downloader.test/v1/jobs/job-1",
        title="Test Song",
        artist="Test Artist",
        spotify_track_id=spotify_key,
        s3_key=f"music/{spotify_key}.mp3",
    )

    async def fake_proxy(_url: str):
        yield b"ID3"

    with (
        patch("app.services.stream_key.fetch_track", new=AsyncMock(return_value=None)),
        patch("app.services.stream_key.start_play", new=AsyncMock(return_value=play)),
        patch("app.services.stream_key._proxy_stream", new=fake_proxy),
        patch("app.services.stream_key._background_ingest", new=AsyncMock()),
    ):
        response = await client.get(f"/api/v1/stream/{spotify_key}", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")


@pytest.mark.asyncio
async def test_search_includes_hits_when_spotify_configured(client: AsyncClient) -> None:
    hits = [
        SpotifyTrackHit(
            key="4uLU6hMCjMI75M1A2tKUQC",
            title="Never Gonna Give You Up",
            artist_name="Rick Astley",
            cover_url="https://example.com/cover.jpg",
            duration_seconds=213,
        )
    ]
    with patch("app.services.search_unified.spotify_configured", return_value=True):
        with patch("app.services.search_unified.spotify_search", new=AsyncMock(return_value=hits)):
            response = await client.get("/api/v1/search", params={"q": "never give"})
    assert response.status_code == 200
    body = response.json()
    assert "hits" in body
    assert body["hits"][0]["key"] == "4uLU6hMCjMI75M1A2tKUQC"
    assert "spotify_id" not in body["hits"][0]
    assert body["hits"][0]["in_catalog"] is False


@pytest.mark.asyncio
async def test_search_local_only_without_spotify(client: AsyncClient) -> None:
    with patch("app.services.search_unified.spotify_configured", return_value=False):
        response = await client.get("/api/v1/search", params={"q": "دوس"})
    assert response.status_code == 200
    body = response.json()
    assert body["track_total"] >= 1
    assert any(h["key"] == "bipolar" for h in body["hits"])
