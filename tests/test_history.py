import uuid
from datetime import UTC, datetime

from httpx import AsyncClient


async def test_play_history_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/me/plays/bipolar")
    assert response.status_code == 401


async def test_record_and_list_recent_history(
    client: AsyncClient, auth_headers: dict[str, str], test_engine
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, Track

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    slugs = [f"hist-a-{suffix}", f"hist-b-{suffix}", f"hist-c-{suffix}"]
    now = datetime.now(UTC)

    async with session_factory() as session:
        artist = Artist(slug=f"hist-artist-{suffix}", name="Hist Artist", name_en=suffix)
        session.add(artist)
        await session.flush()
        for slug in slugs:
            session.add(
                Track(
                    slug=slug,
                    title=slug,
                    artist_id=artist.id,
                    audio_url="https://example.com/x.mp3",
                    published_at=now,
                )
            )
        await session.commit()

    for slug in slugs:
        play = await client.post(f"/api/v1/me/plays/{slug}", headers=auth_headers)
        assert play.status_code == 204

    # replay first track — should dedupe to one entry at top
    replay = await client.post(f"/api/v1/me/plays/{slugs[0]}", headers=auth_headers)
    assert replay.status_code == 204

    history = await client.get("/api/v1/me/history/recent", headers=auth_headers)
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) == 3
    assert items[0]["slug"] == slugs[0]

    delete_one = await client.delete(f"/api/v1/me/history/{slugs[1]}", headers=auth_headers)
    assert delete_one.status_code == 204

    history2 = await client.get("/api/v1/me/history/recent", headers=auth_headers)
    remaining = [t["slug"] for t in history2.json()["items"]]
    assert slugs[1] not in remaining

    clear = await client.delete("/api/v1/me/history", headers=auth_headers)
    assert clear.status_code == 204

    history3 = await client.get("/api/v1/me/history/recent", headers=auth_headers)
    assert history3.json()["items"] == []
