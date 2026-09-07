from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "moziketo-wave"


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "moziketo-wave"


def test_tracks_list() -> None:
    response = client.get("/api/v1/tracks")
    assert response.status_code == 200
    assert "items" in response.json()


def test_track_detail() -> None:
    response = client.get("/api/v1/tracks/sample-track")
    assert response.status_code == 200
    assert response.json()["slug"] == "sample-track"
