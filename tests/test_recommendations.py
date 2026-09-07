import uuid
from datetime import UTC, datetime

from httpx import AsyncClient


async def test_similar_tracks(client: AsyncClient, test_engine) -> None:
    from sqlalchemy import insert
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, Tag, TagKind, Track
    from app.models.associations import track_tags

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)

    async with session_factory() as session:
        artist = Artist(slug=f"sim-artist-{suffix}", name="Sim Artist", name_en=suffix)
        session.add(artist)
        await session.flush()
        tag = Tag(slug=f"sim-pop-{suffix}", name="Pop", kind=TagKind.GENRE)
        session.add(tag)
        await session.flush()
        base = Track(
            slug=f"sim-base-{suffix}",
            title="Base",
            artist_id=artist.id,
            audio_url="https://example.com/base.mp3",
            published_at=now,
            stream_count=10,
        )
        similar = Track(
            slug=f"sim-like-{suffix}",
            title="Like",
            artist_id=artist.id,
            audio_url="https://example.com/like.mp3",
            published_at=now,
            stream_count=5,
        )
        session.add_all([base, similar])
        await session.flush()
        await session.execute(
            insert(track_tags),
            [
                {"track_id": base.id, "tag_id": tag.id},
                {"track_id": similar.id, "tag_id": tag.id},
            ],
        )
        await session.commit()

    response = await client.get(f"/api/v1/tracks/sim-base-{suffix}/similar")
    assert response.status_code == 200
    slugs = [t["slug"] for t in response.json()["items"]]
    assert f"sim-like-{suffix}" in slugs


async def test_personal_recommendations(
    client: AsyncClient, auth_headers: dict[str, str], test_engine
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, Track

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    slug = f"reco-track-{suffix}"
    now = datetime.now(UTC)

    async with session_factory() as session:
        artist = Artist(slug=f"reco-artist-{suffix}", name="Reco Artist", name_en=suffix)
        session.add(artist)
        await session.flush()
        session.add(
            Track(
                slug=slug,
                title="Reco Track",
                artist_id=artist.id,
                audio_url="https://example.com/r.mp3",
                published_at=now,
                stream_count=50,
            )
        )
        await session.commit()

    play = await client.post(f"/api/v1/me/plays/{slug}", headers=auth_headers)
    assert play.status_code == 204

    reco = await client.get("/api/v1/me/recommendations", headers=auth_headers)
    assert reco.status_code == 200
    sections = reco.json()["sections"]
    assert len(sections) >= 1
    assert sections[0]["id"] == "for_you"
