from datetime import date

from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    users_total: int
    users_active: int
    tracks_published: int
    artists_total: int
    albums_published: int
    plays_today: int
    plays_7d: int
    plays_30d: int
    streams_total: int


class RankedTrack(BaseModel):
    slug: str
    title: str
    artist_name: str
    play_count: int


class RankedArtist(BaseModel):
    slug: str
    name: str
    play_count: int


class TimeSeriesPoint(BaseModel):
    day: date
    count: int


class TopTracksResponse(BaseModel):
    period: str
    items: list[RankedTrack]


class TopArtistsResponse(BaseModel):
    period: str
    items: list[RankedArtist]


class TimeSeriesResponse(BaseModel):
    period: str
    points: list[TimeSeriesPoint] = Field(default_factory=list)
