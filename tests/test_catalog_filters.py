from httpx import AsyncClient


async def test_sort_popular(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks", params={"sort": "popular"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["slug"] == "bipolar"
    assert items[0]["stream_count"] >= items[1]["stream_count"]


async def test_filter_genre(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks", params={"genre": "pop"})
    assert response.status_code == 200
    slugs = {t["slug"] for t in response.json()["items"]}
    assert "bipolar" in slugs
    assert "draft-track" not in slugs


async def test_genres_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/genres")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(g["slug"] == "pop" for g in body["items"])


async def test_genre_tracks(client: AsyncClient) -> None:
    response = await client.get("/api/v1/genres/pop/tracks")
    assert response.status_code == 200
    body = response.json()
    assert body["tag"]["slug"] == "pop"
    assert body["total"] >= 2
