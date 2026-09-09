from unittest.mock import patch

from httpx import AsyncClient
from starlette.responses import StreamingResponse


async def _mock_proxy(*_args, range_header=None, **_kwargs):
    async def body():
        yield b"ID3"

    headers = {"Accept-Ranges": "bytes"}
    status_code = 206 if range_header else 200
    if range_header:
        headers["Content-Range"] = "bytes 0-2/*"
    return StreamingResponse(
        body(), status_code=status_code, media_type="audio/mpeg", headers=headers
    )


async def test_stream_proxied(client: AsyncClient) -> None:
    with patch("app.services.audio_proxy.proxy_audio", side_effect=_mock_proxy):
        response = await client.get("/api/v1/tracks/bipolar/stream", follow_redirects=False)
    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-type"].startswith("audio/mpeg")


async def test_stream_range(client: AsyncClient) -> None:
    with patch("app.services.audio_proxy.proxy_audio", side_effect=_mock_proxy):
        response = await client.get(
            "/api/v1/tracks/bipolar/stream",
            headers={"Range": "bytes=0-"},
            follow_redirects=False,
        )
    assert response.status_code == 206
    assert "content-range" in response.headers


async def test_download_redirect(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar/download", follow_redirects=False)
    assert response.status_code == 302
    assert "attachment" in response.headers.get("content-disposition", "")


async def test_unpublished_stream_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/draft-track/stream", follow_redirects=False)
    assert response.status_code == 404
