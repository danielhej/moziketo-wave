import uuid

from httpx import AsyncClient


async def test_patch_profile(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={"display_name": "Updated Name"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"


async def test_change_password(client: AsyncClient) -> None:
    email = f"changepw-{uuid.uuid4().hex[:8]}@moziketo.ir"
    old_password = "securepass1"
    new_password = "newsecure1"

    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_password, "display_name": "PW User"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    change = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert change.status_code == 204

    old = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old.status_code == 401

    new = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new.status_code == 200


async def test_set_password_requires_oauth_only(client: AsyncClient) -> None:
    email = f"setpw-{uuid.uuid4().hex[:8]}@moziketo.ir"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "Has PW"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepass1"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        "/api/v1/auth/set-password",
        headers=headers,
        json={"new_password": "anotherpass1"},
    )
    assert response.status_code == 409
