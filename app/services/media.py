"""Media URL helpers and publish filters for catalog queries."""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func
from sqlalchemy.sql import Select

from app.core.config import get_settings
from app.models import Track


def now_utc() -> datetime:
    return datetime.now(UTC)


def published_track_filter() -> ColumnElement[bool]:
    return (Track.published_at.is_not(None)) & (Track.published_at <= func.now())


def apply_published_filter(stmt: Select[tuple]) -> Select[tuple]:
    return stmt.where(published_track_filter())


def resolve_audio_url(slug: str, stored_url: str | None) -> str | None:
    if stored_url:
        return stored_url
    settings = get_settings()
    return f"{settings.media_base_url.rstrip('/')}/{slug}.mp3"


def resolve_cover_url(slug: str, stored_url: str | None) -> str | None:
    if stored_url:
        return stored_url
    settings = get_settings()
    return f"{settings.media_base_url.rstrip('/')}/{slug}.jpg"
