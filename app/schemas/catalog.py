from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Service health probe — includes database connectivity."""

    status: str = Field(default="ok", examples=["ok"])
    service: str = Field(default="moziketo-wave", examples=["moziketo-wave"])
    version: str = Field(default="0.2.0", examples=["0.2.0"])
    database: str = Field(default="ok", description="PostgreSQL reachability", examples=["ok"])
    redis: str = Field(default="ok", description="Redis reachability", examples=["ok"])
    storage: str = Field(
        default="skipped",
        description="Object storage (S3) reachability",
        examples=["ok", "skipped", "error"],
    )
    oauth_google: Literal["ok", "skipped"] = Field(
        default="skipped",
        description="Google OAuth credentials configured",
        examples=["ok", "skipped"],
    )
    oauth_github: Literal["ok", "skipped"] = Field(
        default="skipped",
        description="GitHub OAuth credentials configured",
        examples=["ok", "skipped"],
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrackSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID")
    slug: str = Field(description="URL-safe identifier", examples=["bipolar"])
    title: str = Field(description="Track title in Persian", examples=["دوسان"])
    artist_name: str = Field(examples=["محسن چاوشی"])
    duration_seconds: int | None = Field(default=None, examples=[245])
    cover_url: str | None = None
    stream_count: int | None = Field(default=None, ge=0, examples=[1234])


class TrackDetail(TrackSummary):
    artist_slug: str = Field(examples=["mohsen-chavoshi"])
    audio_url: str | None = Field(default=None, description="Direct audio file URL")
    description: str | None = None


class TrackListResponse(BaseModel):
    items: list[TrackSummary]
    total: int = Field(description="Total matching tracks")
    page: int
    page_size: int


class ArtistSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str = Field(examples=["mohsen-chavoshi"])
    name: str = Field(examples=["محسن چاوشی"])
    name_en: str | None = Field(default=None, examples=["Mohsen Chavoshi"])
    cover_url: str | None = None
    track_count: int = Field(default=0, ge=0)


class ArtistDetail(ArtistSummary):
    bio: str | None = None
    tracks: list[TrackSummary] = Field(default_factory=list)


class ArtistListResponse(BaseModel):
    items: list[ArtistSummary]
    total: int
    page: int
    page_size: int


class SearchHit(BaseModel):
    """Unified search row — use `key` with GET /stream/{key}."""

    key: str = Field(description="Stream key (Spotify track id or catalog slug)")
    title: str
    artist_name: str
    cover_url: str | None = None
    duration_seconds: int | None = None
    in_catalog: bool = Field(default=False, description="Already in moziketo catalog with audio")
    slug: str | None = Field(default=None, description="Catalog slug when in_catalog")
    play_state: str | None = Field(
        default=None,
        description="ready | buffering | failed — set for non-catalog Spotify hits after prepare",
    )
    buffer_bytes: int | None = Field(
        default=None, description="Downloader buffer when play_state is set"
    )
    job_id: str | None = Field(default=None, description="moz-downloader job id when prepared")


class SearchResponse(BaseModel):
    """Combined search results — Spotify-first hits + local artists."""

    query: str = Field(description="Normalized search query")
    hits: list[SearchHit] = Field(default_factory=list, description="Spotify-first unified results")
    tracks: list[TrackSummary] = Field(default_factory=list)
    artists: list[ArtistSummary] = Field(default_factory=list)
    track_total: int = Field(ge=0)
    artist_total: int = Field(ge=0)
