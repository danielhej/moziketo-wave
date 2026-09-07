import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.fixture
def mock_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_upload(*, kind: str, content: bytes, content_type: str) -> str:
        return f"https://cdn.example.com/uploads/{kind}/fake.jpg"

    monkeypatch.setattr("app.services.storage.upload_bytes", _fake_upload)
    monkeypatch.setattr("app.api.v1.uploads.upload_bytes", _fake_upload)


async def test_admin_upload_requires_key(client: AsyncClient, mock_upload: None) -> None:
    files = {"file": ("cover.jpg", b"fake-image", "image/jpeg")}
    data = {"kind": "cover"}
    response = await client.post("/api/v1/admin/uploads", files=files, data=data)
    assert response.status_code == 403


async def test_admin_upload_success(client: AsyncClient, mock_upload: None) -> None:
    settings = get_settings()
    headers = {"X-Admin-Key": settings.admin_api_key}
    files = {"file": ("cover.jpg", b"fake-image", "image/jpeg")}
    data = {"kind": "cover"}
    response = await client.post(
        "/api/v1/admin/uploads", headers=headers, files=files, data=data
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://cdn.example.com/")


async def test_avatar_upload(
    client: AsyncClient, auth_headers: dict[str, str], mock_upload: None
) -> None:
    files = {"file": ("avatar.png", b"pngbytes", "image/png")}
    response = await client.post("/api/v1/me/uploads/avatar", headers=auth_headers, files=files)
    assert response.status_code == 200
    assert "url" in response.json()

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["avatar_url"] is not None
