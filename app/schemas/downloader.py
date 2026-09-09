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


class DownloaderPlayRequest(BaseModel):
    spotify_url: HttpUrl
    title: str | None = Field(default=None, max_length=300)
    artist: str | None = Field(default=None, max_length=300)
    key: str | None = Field(default=None, max_length=200)


class DownloaderPlayResponse(BaseModel):
    status: str = "starting"
    job_id: str
    stream_url: str
    status_url: str
    title: str
    artist: str
    spotify_track_id: str
    s3_key: str


class DownloaderJobStatusResponse(BaseModel):
    job_id: str
    status: str
    title: str
    artist: str
    spotify_track_id: str
    s3_key: str
    size_bytes: int = 0
    buffer_bytes: int = 0
    direct_ready: bool = False
    download_url: str | None = None
    presigned_url: str | None = None
    error: str | None = None
