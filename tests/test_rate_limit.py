import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.fixture
def low_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "auth_login_ip_limit", 2)
    monkeypatch.setattr(settings, "auth_login_ip_window", 900)
    monkeypatch.setattr(settings, "auth_register_ip_limit", 2)
    monkeypatch.setattr(settings, "auth_register_ip_window", 3600)


async def test_login_rate_limit(client: AsyncClient, low_rate_limits: None) -> None:
    ip = f"10.0.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    email = f"ratelimit-login-{uuid.uuid4().hex[:8]}@moziketo.ir"
    headers = {"X-Forwarded-For": ip}
    payload = {"email": email, "password": "wrongpass1"}
    for _ in range(2):
        response = await client.post("/api/v1/auth/login", json=payload, headers=headers)
        assert response.status_code == 401

    response = await client.post("/api/v1/auth/login", json=payload, headers=headers)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_register_rate_limit(client: AsyncClient, low_rate_limits: None) -> None:
    ip = f"10.1.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    headers = {"X-Forwarded-For": ip}
    for _ in range(2):
        email = f"ratelimit-{uuid.uuid4().hex[:8]}@moziketo.ir"
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "securepass1",
                "display_name": "Rate User",
            },
            headers=headers,
        )
        assert response.status_code == 201

    email = f"ratelimit-{uuid.uuid4().hex[:8]}@moziketo.ir"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass1",
            "display_name": "Rate User",
        },
        headers=headers,
    )
    assert response.status_code == 429
