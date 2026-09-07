from datetime import datetime

from pydantic import BaseModel, Field


class AdminTrackPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    cover_url: str | None = Field(default=None, max_length=500)
    audio_url: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None


class AdminArtistPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    bio: str | None = None
    cover_url: str | None = Field(default=None, max_length=500)


class AdminPlaylistPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    track_slugs: list[str] | None = None
