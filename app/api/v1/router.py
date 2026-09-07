from fastapi import APIRouter

from app.schemas import (
    ArtistListResponse,
    ArtistSummary,
    HealthResponse,
    TrackListResponse,
    TrackSummary,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/tracks", response_model=TrackListResponse, tags=["catalog"])
async def list_tracks(page: int = 1, page_size: int = 24) -> TrackListResponse:
    # Placeholder until DB layer is wired
    return TrackListResponse(items=[], total=0, page=page, page_size=page_size)


@router.get("/tracks/{slug}", response_model=TrackSummary, tags=["catalog"])
async def get_track(slug: str) -> TrackSummary:
    return TrackSummary(
        id="00000000-0000-0000-0000-000000000001",
        slug=slug,
        title="نمونه آهنگ",
        artist_name="هنرمند نمونه",
        duration_seconds=240,
    )


@router.get("/artists", response_model=ArtistListResponse, tags=["catalog"])
async def list_artists(page: int = 1, page_size: int = 24) -> ArtistListResponse:
    return ArtistListResponse(items=[], total=0, page=page, page_size=page_size)


@router.get("/artists/{slug}", response_model=ArtistSummary, tags=["catalog"])
async def get_artist(slug: str) -> ArtistSummary:
    return ArtistSummary(
        id="00000000-0000-0000-0000-000000000002",
        slug=slug,
        name="هنرمند نمونه",
        name_en="Sample Artist",
        track_count=0,
    )
