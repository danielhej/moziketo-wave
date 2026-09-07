from httpx import AsyncClient


async def test_tracks_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["total"] >= 2


async def test_track_detail(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/bipolar")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "bipolar"
    assert body["artist_name"] == "محسن چاوشی"


async def test_track_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/does-not-exist")
    assert response.status_code == 404


async def test_artists_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/artists")
    assert response.status_code == 200
    assert response.json()["total"] >= 2


async def test_artist_detail(client: AsyncClient) -> None:
    response = await client.get("/api/v1/artists/mohsen-chavoshi")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "mohsen-chavoshi"
    assert len(body["tracks"]) >= 1


async def test_search_tracks(client: AsyncClient) -> None:
    response = await client.get("/api/v1/search", params={"q": "دوس"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "دوس"
    assert body["track_total"] >= 1
    assert any(t["slug"] == "bipolar" for t in body["tracks"])


async def test_search_artists(client: AsyncClient) -> None:
    response = await client.get("/api/v1/search", params={"q": "chavoshi"})
    assert response.status_code == 200
    body = response.json()
    assert body["artist_total"] >= 1
    assert any(a["slug"] == "mohsen-chavoshi" for a in body["artists"])


async def test_search_query_too_short(client: AsyncClient) -> None:
    response = await client.get("/api/v1/search", params={"q": "a"})
    assert response.status_code == 422
