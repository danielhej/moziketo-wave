from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import TrackListResponse


class TagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str = Field(examples=["pop"])
    name: str = Field(examples=["پاپ"])
    kind: str = Field(examples=["genre"])
    track_count: int = Field(default=0, ge=0)


class TagListResponse(BaseModel):
    items: list[TagSummary]
    total: int


class TagTrackListResponse(TrackListResponse):
    tag: TagSummary
