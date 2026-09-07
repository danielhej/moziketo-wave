from httpx import AsyncClient

from app.core.config import get_settings


async def test_admin_catalog_summary(client: AsyncClient) -> None:
    settings = get_settings()
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.get("/api/v1/admin/catalog/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "tracks_total" in body
    assert "users_total" in body


async def test_admin_users_list(client: AsyncClient) -> None:
    settings = get_settings()
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["total"] >= 0


async def test_admin_import_status(client: AsyncClient) -> None:
    settings = get_settings()
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.get("/api/v1/admin/import/status", headers=headers)
    assert response.status_code == 200
