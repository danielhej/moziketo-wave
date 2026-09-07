import uuid

from httpx import AsyncClient


async def test_change_email_and_export(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    new_email = f"new-{uuid.uuid4().hex[:8]}@moziketo.ir"
    response = await client.post(
        "/api/v1/auth/me/change-email",
        headers=auth_headers,
        json={"new_email": new_email},
    )
    assert response.status_code == 200
    token = response.json()["change_email_token"]
    assert token

    confirm = await client.get(
        "/api/v1/auth/me/change-email/confirm",
        params={"token": token},
    )
    assert confirm.status_code == 204

    export = await client.get("/api/v1/auth/me/export", headers=auth_headers)
    assert export.status_code == 200
    body = export.json()
    assert body["profile"]["email"] == new_email
    assert "favorites" in body


async def test_delete_account(client: AsyncClient) -> None:
    email = f"delete-{uuid.uuid4().hex[:8]}@moziketo.ir"
    password = "deletepass1"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Delete Me"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    delete = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers=headers,
        json={"password": password, "confirm": True},
    )
    assert delete.status_code == 204

    login_again = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_again.status_code == 401
