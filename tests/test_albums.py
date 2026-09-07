import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.core.config import get_settings


async def _admin_headers() -> dict[str, str]:
    settings = get_settings()
    return {"X-Admin-Key": settings.admin_api_key}


async def test_list_and_get_published_album(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Album, Artist, Track

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    artist_slug = f"album-artist-{suffix}"
    album_slug = f"test-album-{suffix}"
    track_slug = f"album-track-{suffix}"
    now = datetime.now(UTC)

    async with session_factory() as session:
        artist = Artist(slug=artist_slug, name="Album Artist", name_en=artist_slug)
        session.add(artist)
        await session.flush()
        album = Album(
            slug=album_slug,
            title="Test Album",
            artist_id=artist.id,
            published_at=now,
        )
        session.add(album)
        await session.flush()
        session.add(
            Track(
                slug=track_slug,
                title="Album Track",
                artist_id=artist.id,
                album_id=album.id,
                audio_url="https://example.com/track.mp3",
                published_at=now,
            )
        )
        await session.commit()

    listing = await client.get("/api/v1/albums")
    assert listing.status_code == 200
    slugs = [item["slug"] for item in listing.json()["items"]]
    assert album_slug in slugs

    detail = await client.get(f"/api/v1/albums/{album_slug}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Test Album"
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["slug"] == track_slug


async def test_unpublished_album_hidden(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Album, Artist

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    slug = f"draft-album-{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        artist = Artist(slug=f"artist-{slug}", name="A", name_en=slug)
        session.add(artist)
        await session.flush()
        session.add(
            Album(slug=slug, title="Draft", artist_id=artist.id, published_at=None)
        )
        await session.commit()

    response = await client.get(f"/api/v1/albums/{slug}")
    assert response.status_code == 404


async def test_admin_create_publish_album(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models import Artist, Track

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    artist_slug = f"admin-album-artist-{suffix}"
    track_slug = f"admin-album-track-{suffix}"
    album_slug = f"admin-created-album-{suffix}"
    now = datetime.now(UTC)

    async with session_factory() as session:
        artist = Artist(slug=artist_slug, name="Admin Album Artist", name_en=artist_slug)
        session.add(artist)
        await session.flush()
        session.add(
            Track(
                slug=track_slug,
                title="Track",
                artist_id=artist.id,
                audio_url="https://example.com/a.mp3",
                published_at=now,
            )
        )
        await session.commit()

    headers = await _admin_headers()
    create = await client.post(
        "/api/v1/admin/albums",
        headers=headers,
        json={
            "slug": album_slug,
            "title": "Created Album",
            "artist_slug": artist_slug,
            "track_slugs": [track_slug],
        },
    )
    assert create.status_code == 201

    public = await client.get(f"/api/v1/albums/{album_slug}")
    assert public.status_code == 404

    publish = await client.post(f"/api/v1/admin/albums/{album_slug}/publish", headers=headers)
    assert publish.status_code == 204

    public2 = await client.get(f"/api/v1/albums/{album_slug}")
    assert public2.status_code == 200
    assert public2.json()["tracks"][0]["slug"] == track_slug
