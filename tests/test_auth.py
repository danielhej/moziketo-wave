import uuid

from httpx import AsyncClient


async def test_register_and_login(client: AsyncClient) -> None:
    email = f"user1-{uuid.uuid4().hex[:8]}@moziketo.ir"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass1",
            "display_name": "User One",
        },
    )
    assert reg.status_code == 201
    assert reg.json()["email"] == email

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepass1"},
    )
    assert login.status_code == 200
    body = login.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_invalid(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@moziketo.ir", "password": "wrong"},
    )
    assert response.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_token(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert "@moziketo.ir" in response.json()["email"]


async def test_refresh_token(client: AsyncClient) -> None:
    email = f"refresh-{uuid.uuid4().hex[:8]}@moziketo.ir"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass1",
            "display_name": "Refresh User",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepass1"},
    )
    refresh_token = login.json()["refresh_token"]
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()
