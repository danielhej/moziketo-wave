from httpx import AsyncClient


async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "moziketo-wave"


async def test_openapi(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Moziketo Wave"
    assert schema["openapi"].startswith("3.")
    assert any(s["url"] == "https://api.moziketo.ir" for s in schema["servers"])
    paths = schema["paths"]
    assert "/api/v1/tracks" in paths
    assert "/api/v1/artists/{slug}" in paths
    assert "/api/v1/search" in paths
    tag_names = {t["name"] for t in schema["tags"]}
    assert "catalog" in tag_names
    assert "system" in tag_names


async def test_swagger_ui(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


async def test_swagger_redirect(client: AsyncClient) -> None:
    response = await client.get("/swagger", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] in ("ok", "error")
