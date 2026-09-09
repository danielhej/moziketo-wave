from pydantic import BaseModel, Field, HttpUrl


class DownloaderIngestRequest(BaseModel):
    spotify_url: HttpUrl
    title: str | None = Field(default=None, max_length=300)
    artist: str | None = Field(default=None, max_length=300)
    key: str | None = Field(
        default=None,
        description="Optional S3 basename, e.g. track-slug.mp3",
        max_length=200,
    )


class DownloaderIngestResponse(BaseModel):
    status: str = "ok"
    download_url: str
    presigned_url: str | None = None
    s3_key: str
    title: str | None = None
    artist: str | None = None
    size_bytes: int
    spotify_track_id: str | None = None
