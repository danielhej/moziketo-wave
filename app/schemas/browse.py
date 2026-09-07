from pydantic import BaseModel, Field

from app.schemas.catalog import TrackSummary


class BrowseSection(BaseModel):
    id: str = Field(description="Section identifier", examples=["popular"])
    title: str = Field(description="Display title", examples=["پربازدید"])
    tracks: list[TrackSummary] = Field(default_factory=list)


class BrowseResponse(BaseModel):
    sections: list[BrowseSection] = Field(default_factory=list)
