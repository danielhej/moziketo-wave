from httpx import AsyncClient


async def test_stream_redirect(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar/stream", follow_redirects=False)
    assert response.status_code == 302
    assert "bipolar.mp3" in response.headers["location"]


async def test_download_redirect(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar/download", follow_redirects=False)
    assert response.status_code == 302
    assert "attachment" in response.headers.get("content-disposition", "")


async def test_unpublished_stream_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/draft-track/stream", follow_redirects=False)
    assert response.status_code == 404
