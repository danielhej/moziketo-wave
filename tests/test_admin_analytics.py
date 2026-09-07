import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.core.config import get_settings


async def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": get_settings().admin_api_key}


async def test_analytics_overview(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, PlayEvent, Track, User

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)

    async with session_factory() as session:
        user = User(
            email=f"analytics-{suffix}@moziketo.ir",
            password_hash="x",
            display_name="Analytics User",
        )
        session.add(user)
        artist = Artist(slug=f"an-artist-{suffix}", name="An Artist", name_en=suffix)
        session.add(artist)
        await session.flush()
        track = Track(
            slug=f"an-track-{suffix}",
            title="An Track",
            artist_id=artist.id,
            audio_url="https://example.com/a.mp3",
            published_at=now,
            stream_count=3,
        )
        session.add(track)
        await session.flush()
        session.add(PlayEvent(user_id=user.id, track_id=track.id, played_at=now))
        await session.commit()

    headers = await _admin_headers()
    overview = await client.get("/api/v1/admin/analytics/overview", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert body["users_total"] >= 1
    assert body["plays_today"] >= 1
    assert body["streams_total"] >= 3

    top = await client.get("/api/v1/admin/analytics/top-tracks?period=7d", headers=headers)
    assert top.status_code == 200
    assert len(top.json()["items"]) >= 1

    plays = await client.get("/api/v1/admin/analytics/plays?period=30d", headers=headers)
    assert plays.status_code == 200
    assert len(plays.json()["points"]) >= 1


async def test_analytics_forbidden(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/analytics/overview")
    assert response.status_code == 403
