import uuid

import pytest
from httpx import AsyncClient

from app.core.redis import connect_redis, get_redis
from app.models import OAuthProvider


async def test_oauth_unknown_provider(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/oauth/unknown-provider",
        follow_redirects=False,
    )
    assert response.status_code == 422


async def test_oauth_unconfigured_provider(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/auth/oauth/{OAuthProvider.GOOGLE}",
        follow_redirects=False,
    )
    assert response.status_code == 503


async def test_oauth_exchange_invalid_code(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/oauth/exchange",
        json={"code": "invalid-oauth-exchange-code"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("provider", OAuthProvider.ALL)
async def test_oauth_unconfigured_providers(client: AsyncClient, provider: str) -> None:
    response = await client.get(
        f"/api/v1/auth/oauth/{provider}",
        follow_redirects=False,
    )
    assert response.status_code == 503


async def test_oauth_exchange_success(client: AsyncClient) -> None:
    email = f"oauth-{uuid.uuid4().hex[:8]}@moziketo.ir"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "OAuth User"},
    )
    user_id = reg.json()["id"]

    await connect_redis()
    redis = get_redis()
    code = f"test-code-{uuid.uuid4().hex}"
    await redis.set(f"oauth_code:{code}", user_id, ex=60)

    response = await client.post("/api/v1/auth/oauth/exchange", json={"code": code})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body

    second = await client.post("/api/v1/auth/oauth/exchange", json={"code": code})
    assert second.status_code == 401
