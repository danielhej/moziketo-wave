from httpx import AsyncClient


async def test_add_list_remove_favorite(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    add = await client.post("/api/v1/me/favorites/bipolar", headers=auth_headers)
    assert add.status_code == 201
    assert add.json()["slug"] == "bipolar"

    listing = await client.get("/api/v1/me/favorites", headers=auth_headers)
    assert listing.status_code == 200
    slugs = [t["slug"] for t in listing.json()["items"]]
    assert "bipolar" in slugs

    removed = await client.delete("/api/v1/me/favorites/bipolar", headers=auth_headers)
    assert removed.status_code == 204


async def test_favorites_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me/favorites")
    assert response.status_code == 401
