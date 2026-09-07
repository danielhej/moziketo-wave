"""Seed demo catalog data for Moziketo Wave."""

import asyncio

from sqlalchemy import select

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


async def seed() -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(Artist.id).limit(1))
        if existing is not None:
            print("Seed skipped — data already exists")
            return

        artist_map: dict[str, Artist] = {}
        for row in SAMPLE_ARTISTS:
            artist = Artist(**row)
            session.add(artist)
            artist_map[row["slug"]] = artist

        await session.flush()

        for row in SAMPLE_TRACKS:
            session.add(
                Track(
                    slug=row["slug"],
                    title=row["title"],
                    artist_id=artist_map[row["artist_slug"]].id,
                    duration_seconds=row["duration_seconds"],
                )
            )

        await session.commit()
        print(f"Seeded {len(SAMPLE_ARTISTS)} artists and {len(SAMPLE_TRACKS)} tracks")


if __name__ == "__main__":
    asyncio.run(seed())
