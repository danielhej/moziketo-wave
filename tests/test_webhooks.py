from httpx import AsyncClient

from app.core.config import get_settings
from app.models.webhook import WebhookEvent


async def test_webhook_crud(client: AsyncClient) -> None:
    settings = get_settings()
    headers = {"X-Admin-Key": settings.admin_api_key}

    create = await client.post(
        "/api/v1/admin/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hook",
            "secret": "supersecret123",
            "events": [WebhookEvent.IMPORT_COMPLETED],
        },
    )
    assert create.status_code == 201
    sub_id = create.json()["id"]

    listing = await client.get("/api/v1/admin/webhooks", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    test = await client.post(f"/api/v1/admin/webhooks/{sub_id}/test", headers=headers)
    assert test.status_code == 200

    delete = await client.delete(f"/api/v1/admin/webhooks/{sub_id}", headers=headers)
    assert delete.status_code == 204
