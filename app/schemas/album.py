from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import TrackSummary


class AlbumSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    artist_name: str
    artist_slug: str
    cover_url: str | None = None
    track_count: int = Field(default=0, ge=0)


class AlbumDetail(AlbumSummary):
    description: str | None = None
    published_at: datetime | None = None
    tracks: list[TrackSummary] = Field(default_factory=list)


class AlbumListResponse(BaseModel):
    items: list[AlbumSummary]
    total: int
    page: int
    page_size: int
