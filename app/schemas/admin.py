from pydantic import BaseModel, Field


class ImportResult(BaseModel):
    artists_upserted: int = 0
    tracks_upserted: int = 0
    tags_upserted: int = 0
    playlists_upserted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
