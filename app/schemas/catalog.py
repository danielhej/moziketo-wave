from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "moziketo-wave"
    version: str = "0.1.0"
    database: str = "ok"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrackSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    artist_name: str
    duration_seconds: int | None = None
    cover_url: str | None = None


class TrackDetail(TrackSummary):
    artist_slug: str
    audio_url: str | None = None
    description: str | None = None


class TrackListResponse(BaseModel):
    items: list[TrackSummary]
    total: int
    page: int
    page_size: int


class ArtistSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    name_en: str | None = None
    cover_url: str | None = None
    track_count: int = 0


class ArtistDetail(ArtistSummary):
    bio: str | None = None
    tracks: list[TrackSummary] = Field(default_factory=list)


class ArtistListResponse(BaseModel):
    items: list[ArtistSummary]
    total: int
    page: int
    page_size: int
