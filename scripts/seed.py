"""Seed demo catalog data for Moziketo Wave."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Artist, Playlist, PlaylistKind, PlaylistTrack, Tag, TagKind, Track

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
        "stream_count": 100,
        "audio_url": "https://moziketo.s3.ir-thr-at1.arvanstorage.ir/2024-01%2FTaylor-Swift-Cruel-Summer.mp3",
        "cover_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d00001e02e787cffec20aa2a396a61647",
        "genres": [("pop", "پاپ")],
    },
    {
        "slug": "khabarat-shod",
        "title": "خبرت شد",
        "artist_slug": "sirvan-khosravi",
        "duration_seconds": 231,
        "stream_count": 50,
        "audio_url": "https://moziketo.s3.ir-thr-at1.arvanstorage.ir/2024-01%2FImagine-Dragons-Believer.mp3",
        "cover_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d00001e025675e83f707f1d7271e5cf8a",
        "genres": [("pop", "پاپ")],
    },
]

EDITORIAL_PLAYLIST = {
    "slug": "the-hot-100",
    "title": "The Hot 100",
    "track_slugs": ["bipolar", "khabarat-shod"],
}

UNPUBLISHED_TRACK = {
    "slug": "draft-track",
    "title": "پیش‌نویس",
    "artist_slug": "mohsen-chavoshi",
    "duration_seconds": 180,
}


async def _ensure_tags_and_playlist(session, track_map: dict[str, Track]) -> None:
    pop = await session.scalar(
        select(Tag).where(Tag.slug == "pop", Tag.kind == TagKind.GENRE)
    )
    if pop is None:
        pop = Tag(slug="pop", name="پاپ", kind=TagKind.GENRE)
        session.add(pop)
        await session.flush()

    for track in track_map.values():
        if pop not in track.tags:
            track.tags.append(pop)

    existing_pl = await session.scalar(
        select(Playlist).where(Playlist.slug == EDITORIAL_PLAYLIST["slug"])
    )
    if existing_pl is None:
        playlist = Playlist(
            slug=EDITORIAL_PLAYLIST["slug"],
            title=EDITORIAL_PLAYLIST["title"],
            kind=PlaylistKind.EDITORIAL,
            published_at=datetime.now(UTC),
        )
        session.add(playlist)
        await session.flush()
        for position, slug in enumerate(EDITORIAL_PLAYLIST["track_slugs"]):
            track = track_map.get(slug)
            if track is not None:
                session.add(
                    PlaylistTrack(
                        playlist_id=playlist.id,
                        track_id=track.id,
                        position=position,
                    )
                )


async def seed() -> None:
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        existing = await session.scalar(select(Artist.id).limit(1))
        if existing is not None:
            now = datetime.now(UTC)
            tracks = (await session.scalars(select(Track))).all()
            updated = False
            track_map = {t.slug: t for t in tracks}
            sample_by_slug = {row["slug"]: row for row in SAMPLE_TRACKS}
            for track in tracks:
                sample = sample_by_slug.get(track.slug)
                if sample:
                    audio = sample.get("audio_url")
                    if audio and (
                        not track.audio_url or "dl.moziketo.ir" in (track.audio_url or "")
                    ):
                        track.audio_url = audio
                        updated = True
                    cover = sample.get("cover_url")
                    if cover and (
                        not track.cover_url or "dl.moziketo.ir" in (track.cover_url or "")
                    ):
                        track.cover_url = cover
                        updated = True
                if track.published_at is None and track.slug != UNPUBLISHED_TRACK["slug"]:
                    track.published_at = now
                    updated = True
                if track.slug == "bipolar" and track.stream_count == 0:
                    track.stream_count = 100
                    updated = True
                if track.slug == "khabarat-shod" and track.stream_count == 0:
                    track.stream_count = 50
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
            pl_exists = await session.scalar(
                select(Playlist.id).where(Playlist.slug == EDITORIAL_PLAYLIST["slug"])
            )
            if pl_exists is None and track_map:
                await _ensure_tags_and_playlist(session, track_map)
                updated = True
            elif track_map:
                pop = await session.scalar(
                    select(Tag).where(Tag.slug == "pop", Tag.kind == TagKind.GENRE)
                )
                if pop is None:
                    await _ensure_tags_and_playlist(session, track_map)
                    updated = True
            if updated:
                await session.commit()
                print("Backfilled seed extensions")
            else:
                print("Seed skipped — data already exists")
            return

        artist_map: dict[str, Artist] = {}
        for row in SAMPLE_ARTISTS:
            artist = Artist(**row)
            session.add(artist)
            artist_map[row["slug"]] = artist

        await session.flush()

        track_map: dict[str, Track] = {}
        for row in SAMPLE_TRACKS:
            track = Track(
                slug=row["slug"],
                title=row["title"],
                artist_id=artist_map[row["artist_slug"]].id,
                duration_seconds=row["duration_seconds"],
                stream_count=row.get("stream_count", 0),
                audio_url=row["audio_url"],
                cover_url=row["cover_url"],
                published_at=now,
            )
            session.add(track)
            track_map[row["slug"]] = track

        session.add(
            Track(
                slug=UNPUBLISHED_TRACK["slug"],
                title=UNPUBLISHED_TRACK["title"],
                artist_id=artist_map[UNPUBLISHED_TRACK["artist_slug"]].id,
                duration_seconds=UNPUBLISHED_TRACK["duration_seconds"],
                published_at=None,
            )
        )

        await session.flush()
        await _ensure_tags_and_playlist(session, track_map)
        await session.commit()
        print(f"Seeded {len(SAMPLE_ARTISTS)} artists and {len(SAMPLE_TRACKS) + 1} tracks")


if __name__ == "__main__":
    asyncio.run(seed())
