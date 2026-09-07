import uuid

from httpx import AsyncClient


async def test_password_reset_flow(client: AsyncClient) -> None:
    email = f"reset-{uuid.uuid4().hex[:8]}@moziketo.ir"
    password = "securepass1"
    new_password = "newsecure1"

    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Reset User"},
    )

    forgot = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    body = forgot.json()
    assert "reset_token" in body
    assert body["expires_in"] > 0

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": body["reset_token"], "new_password": new_password},
    )
    assert reset.status_code == 204

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200


async def test_forgot_password_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing-user@moziketo.ir"},
    )
    assert response.status_code == 204


async def test_reset_password_invalid_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-valid-token", "new_password": "newsecure1"},
    )
    assert response.status_code == 400
