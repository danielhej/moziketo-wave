import uuid

from httpx import AsyncClient

from app.core.config import get_settings


async def _admin_headers() -> dict[str, str]:
    settings = get_settings()
    return {"X-Admin-Key": settings.admin_api_key}


async def test_publish_unpublish_track(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, Track

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    artist_slug = f"admin-artist-{suffix}"
    slug = f"admin-test-track-{suffix}"
    async with session_factory() as session:
        artist = Artist(slug=artist_slug, name="Admin Artist", name_en=artist_slug)
        session.add(artist)
        await session.flush()
        track = Track(
            slug=slug,
            title="Admin Track",
            artist_id=artist.id,
            audio_url="https://dl.moziketo.ir/music/test.mp3",
            published_at=None,
        )
        session.add(track)
        await session.commit()

    headers = await _admin_headers()

    public = await client.get(f"/api/v1/tracks/{slug}")
    assert public.status_code == 404

    publish = await client.post(f"/api/v1/admin/tracks/{slug}/publish", headers=headers)
    assert publish.status_code == 204

    public2 = await client.get(f"/api/v1/tracks/{slug}")
    assert public2.status_code == 200

    unpublish = await client.post(f"/api/v1/admin/tracks/{slug}/unpublish", headers=headers)
    assert unpublish.status_code == 204

    public3 = await client.get(f"/api/v1/tracks/{slug}")
    assert public3.status_code == 404


async def test_patch_artist(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    slug = f"admin-patch-artist-{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        session.add(Artist(slug=slug, name="Old Name", name_en=slug))
        await session.commit()

    headers = await _admin_headers()
    patch = await client.patch(
        f"/api/v1/admin/artists/{slug}",
        headers=headers,
        json={"name": "New Name"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "New Name"

    detail = await client.get(f"/api/v1/artists/{slug}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "New Name"
