"""Seed demo catalog data for Moziketo Wave."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Artist, Track

SAMPLE_ARTISTS = [
    {
        "slug": "mohsen-chavoshi",
        "name": "محسن چاوشی",
        "name_en": "Mohsen Chavoshi",
        "bio": "خواننده، آهنگساز و نوازنده ایرانی.",
    },
    {
        "slug": "sirvan-khosravi",
        "name": "سیروان خسروی",
        "name_en": "Sirvan Khosravi",
        "bio": "خواننده و آهنگساز پاپ راک ایرانی.",
    },
]

SAMPLE_TRACKS = [
    {
        "slug": "bipolar",
        "title": "دوسان",
        "artist_slug": "mohsen-chavoshi",
        "duration_seconds": 245,
    },
    {
        "slug": "khabarat-shod",
        "title": "خبرت شد",
        "artist_slug": "sirvan-khosravi",
        "duration_seconds": 231,
    },
]

UNPUBLISHED_TRACK = {
    "slug": "draft-track",
    "title": "پیش‌نویس",
    "artist_slug": "mohsen-chavoshi",
    "duration_seconds": 180,
}


async def seed() -> None:
    settings = get_settings()
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        existing = await session.scalar(select(Artist.id).limit(1))
        if existing is not None:
            now = datetime.now(UTC)
            tracks = (await session.scalars(select(Track))).all()
            updated = False
            for track in tracks:
                if track.published_at is None and track.slug != UNPUBLISHED_TRACK["slug"]:
                    track.published_at = now
                    track.audio_url = track.audio_url or (
                        f"{settings.media_base_url.rstrip('/')}/{track.slug}.mp3"
                    )
                    updated = True
            draft = await session.scalar(
                select(Track).where(Track.slug == UNPUBLISHED_TRACK["slug"])
            )
            if draft is None:
                artist = await session.scalar(
                    select(Artist).where(Artist.slug == UNPUBLISHED_TRACK["artist_slug"])
                )
                if artist is not None:
                    session.add(
                        Track(
                            slug=UNPUBLISHED_TRACK["slug"],
                            title=UNPUBLISHED_TRACK["title"],
                            artist_id=artist.id,
                            duration_seconds=UNPUBLISHED_TRACK["duration_seconds"],
                            published_at=None,
                        )
                    )
                    updated = True
            if updated:
                await session.commit()
                print("Backfilled publish dates and draft track")
            else:
                print("Seed skipped — data already exists")
            return

        artist_map: dict[str, Artist] = {}
        for row in SAMPLE_ARTISTS:
            artist = Artist(**row)
            session.add(artist)
            artist_map[row["slug"]] = artist

        await session.flush()

        for row in SAMPLE_TRACKS:
            slug = row["slug"]
            session.add(
                Track(
                    slug=slug,
                    title=row["title"],
                    artist_id=artist_map[row["artist_slug"]].id,
                    duration_seconds=row["duration_seconds"],
                    audio_url=f"{settings.media_base_url.rstrip('/')}/{slug}.mp3",
                    cover_url=f"{settings.media_base_url.rstrip('/')}/{slug}.jpg",
                    published_at=now,
                )
            )

        session.add(
            Track(
                slug=UNPUBLISHED_TRACK["slug"],
                title=UNPUBLISHED_TRACK["title"],
                artist_id=artist_map[UNPUBLISHED_TRACK["artist_slug"]].id,
                duration_seconds=UNPUBLISHED_TRACK["duration_seconds"],
                published_at=None,
            )
        )

        await session.commit()
        print(f"Seeded {len(SAMPLE_ARTISTS)} artists and {len(SAMPLE_TRACKS) + 1} tracks")


if __name__ == "__main__":
    asyncio.run(seed())
