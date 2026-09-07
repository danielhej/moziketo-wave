from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import TrackSummary


class PlaylistSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str = Field(examples=["the-hot-100"])
    title: str = Field(examples=["The Hot 100"])
    cover_url: str | None = None
    description: str | None = None
    kind: str = Field(examples=["editorial"])
    track_count: int = Field(default=0, ge=0)


class PlaylistDetail(PlaylistSummary):
    tracks: list[TrackSummary] = Field(default_factory=list)
    published_at: datetime | None = None


class PlaylistListResponse(BaseModel):
    items: list[PlaylistSummary]
    total: int


class CreatePlaylistRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    track_slugs: list[str] = Field(default_factory=list)


class UpdatePlaylistRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    track_slugs: list[str] | None = None
