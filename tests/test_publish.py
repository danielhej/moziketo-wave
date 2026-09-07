from httpx import AsyncClient


async def test_unpublished_hidden_from_list(client: AsyncClient) -> None:
    detail = await client.get("/api/v1/tracks/bipolar")
    assert detail.status_code == 200
    draft = await client.get("/api/v1/tracks/draft-track")
    assert draft.status_code == 404
    response = await client.get("/api/v1/tracks")
    assert response.status_code == 200
    slugs = [t["slug"] for t in response.json()["items"]]
    assert "draft-track" not in slugs


async def test_unpublished_detail_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/draft-track")
    assert response.status_code == 404


async def test_track_has_stored_audio_url(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar")
    assert response.status_code == 200
    body = response.json()
    assert body["audio_url"] is not None
    assert "arvanstorage" in body["audio_url"]
    assert body["cover_url"] is not None
    assert "dl.moziketo.ir" not in body["cover_url"]
