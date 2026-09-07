from httpx import AsyncClient


async def test_browse_sections(client: AsyncClient) -> None:
    response = await client.get("/api/v1/browse")
    assert response.status_code == 200
    body = response.json()
    section_ids = {s["id"] for s in body["sections"]}
    assert section_ids == {"popular", "latest", "new_release"}
    popular = next(s for s in body["sections"] if s["id"] == "popular")
    assert len(popular["tracks"]) >= 1
    assert popular["tracks"][0]["slug"] == "bipolar"


async def test_browse_popular_order(client: AsyncClient) -> None:
    response = await client.get("/api/v1/browse")
    popular = next(s for s in response.json()["sections"] if s["id"] == "popular")
    counts = [t["stream_count"] for t in popular["tracks"]]
    assert counts == sorted(counts, reverse=True)
