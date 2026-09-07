from httpx import AsyncClient


async def test_editorial_playlists(client: AsyncClient) -> None:
    response = await client.get("/api/v1/playlists")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(p["slug"] == "the-hot-100" for p in body["items"])


async def test_editorial_playlist_detail(client: AsyncClient) -> None:
    response = await client.get("/api/v1/playlists/the-hot-100")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "the-hot-100"
    assert len(body["tracks"]) == 2


async def test_user_playlist_crud(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post(
        "/api/v1/me/playlists",
        json={"title": "My Mix", "track_slugs": ["bipolar"]},
        headers=auth_headers,
    )
    assert create.status_code == 201
    playlist_id = create.json()["id"]
    assert create.json()["track_count"] == 1

    listing = await client.get("/api/v1/me/playlists", headers=auth_headers)
    assert listing.status_code == 200
    assert any(p["id"] == playlist_id for p in listing.json()["items"])

    add = await client.post(
        f"/api/v1/me/playlists/{playlist_id}/tracks/khabarat-shod",
        headers=auth_headers,
    )
    assert add.status_code == 200
    assert add.json()["track_count"] == 2

    remove = await client.delete(
        f"/api/v1/me/playlists/{playlist_id}/tracks/bipolar",
        headers=auth_headers,
    )
    assert remove.status_code == 200
    assert remove.json()["track_count"] == 1

    delete = await client.delete(
        f"/api/v1/me/playlists/{playlist_id}",
        headers=auth_headers,
    )
    assert delete.status_code == 204
