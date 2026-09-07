from httpx import AsyncClient


async def test_unpublished_hidden_from_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks")
    assert response.status_code == 200
    slugs = [t["slug"] for t in response.json()["items"]]
    assert "draft-track" not in slugs
    assert "bipolar" in slugs


async def test_unpublished_detail_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/draft-track")
    assert response.status_code == 404


async def test_track_has_resolved_audio_url(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar")
    assert response.status_code == 200
    assert response.json()["audio_url"].endswith("bipolar.mp3")
