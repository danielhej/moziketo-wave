import uuid

from httpx import AsyncClient

from app.core.config import get_settings


async def test_public_search_rate_limit(client: AsyncClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "public_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "public_search_ip_limit", 2)
    monkeypatch.setattr(settings, "public_search_ip_window", 60)

    ip = f"10.2.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    headers = {"X-Forwarded-For": ip}

    for _ in range(2):
        response = await client.get(
            "/api/v1/search", params={"q": "ratelimit"}, headers=headers
        )
        assert response.status_code == 200
    response = await client.get(
        "/api/v1/search", params={"q": "ratelimit"}, headers=headers
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers
