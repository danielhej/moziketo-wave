import uuid

from httpx import AsyncClient


async def test_email_verification_flow(client: AsyncClient) -> None:
    email = f"verify-{uuid.uuid4().hex[:8]}@moziketo.ir"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "Verify User"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["user"]["email_verified"] is False
    assert body.get("verify_token")

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepass1"},
    )
    assert login.status_code == 200

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.json()["email_verified"] is False

    confirm = await client.get(
        f"/api/v1/auth/verify-email/confirm?token={body['verify_token']}"
    )
    assert confirm.status_code == 204

    me2 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me2.json()["email_verified"] is True


async def test_verify_email_request_resend(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/auth/verify-email/request",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "verify_token" in response.json()


async def test_verify_email_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/verify-email/confirm?token=invalid-token-value")
    assert response.status_code == 400
