from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import Track


async def test_stream_increments_play_count(client: AsyncClient) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        before = await session.scalar(select(Track.stream_count).where(Track.slug == "bipolar"))

    response = await client.get("/api/v1/tracks/bipolar/stream", follow_redirects=False)
    assert response.status_code in (200, 206)
    assert response.headers["content-type"].startswith("audio/")

    async with session_factory() as session:
        after = await session.scalar(select(Track.stream_count).where(Track.slug == "bipolar"))

    await engine.dispose()
    assert after == before + 1
