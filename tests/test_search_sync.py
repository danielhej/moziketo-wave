from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.services.search_sync import sync_track


@pytest.fixture
def meili_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.search_sync.meili_available", lambda: True)


async def test_sync_track_upserts_published(
    meili_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    upsert = AsyncMock()
    delete = AsyncMock()
    build_doc = AsyncMock(return_value={"id": "1", "slug": "test", "published": True})
    monkeypatch.setattr("app.services.search_sync.upsert_documents", upsert)
    monkeypatch.setattr("app.services.search_sync.delete_document", delete)
    monkeypatch.setattr("app.services.search_sync.build_track_doc", build_doc)

    track = MagicMock()
    track.id = "11111111-1111-1111-1111-111111111111"
    track.slug = "test"
    track.published_at = datetime.now(UTC)
    session = AsyncMock()

    await sync_track(session, track)

    upsert.assert_awaited_once_with("tracks", [{"id": "1", "slug": "test", "published": True}])
    delete.assert_not_awaited()


async def test_sync_track_deletes_unpublished(
    meili_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    upsert = AsyncMock()
    delete = AsyncMock()
    monkeypatch.setattr("app.services.search_sync.upsert_documents", upsert)
    monkeypatch.setattr("app.services.search_sync.delete_document", delete)

    track = MagicMock()
    track.id = "11111111-1111-1111-1111-111111111111"
    track.slug = "test"
    track.published_at = None
    session = AsyncMock()

    await sync_track(session, track)

    delete.assert_awaited_once_with("tracks", "11111111-1111-1111-1111-111111111111")
    upsert.assert_not_awaited()


async def test_admin_webhook_retry_queues(client: AsyncClient, monkeypatch) -> None:
    settings = get_settings()

    async def _noop_dispatch(kind: str, job_id: str, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.services.jobs._dispatch", _noop_dispatch)
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.post("/api/v1/admin/jobs/webhooks/retry", headers=headers)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = await client.get(f"/api/v1/admin/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["kind"] == "webhook_delivery"


async def test_admin_prune_plays_queues(client: AsyncClient, monkeypatch) -> None:
    settings = get_settings()

    async def _noop_dispatch(kind: str, job_id: str, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.services.jobs._dispatch", _noop_dispatch)
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.post("/api/v1/admin/jobs/prune-plays", headers=headers)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = await client.get(f"/api/v1/admin/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["kind"] == "prune_play_events"
