from httpx import AsyncClient

from app.core.config import get_settings


async def test_admin_import_queues_job(client: AsyncClient, monkeypatch) -> None:
    settings = get_settings()

    async def _noop_dispatch(kind: str, job_id: str, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.services.jobs._dispatch", _noop_dispatch)
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = await client.post("/api/v1/admin/import?limit=1", headers=headers)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = await client.get(f"/api/v1/admin/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "queued"
