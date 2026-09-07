"""Media URL helpers and publish filters for catalog queries."""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func
from sqlalchemy.sql import Select

from app.models import Track


def now_utc() -> datetime:
    return datetime.now(UTC)


def published_track_filter() -> ColumnElement[bool]:
    return (Track.published_at.is_not(None)) & (Track.published_at <= func.now())


def apply_published_filter(stmt: Select[tuple]) -> Select[tuple]:
    return stmt.where(published_track_filter())


def resolve_audio_url(_slug: str, stored_url: str | None) -> str | None:
    """Return stored URL only — never synthesize placeholder media paths."""
    if not stored_url:
        return None
    url = stored_url.strip()
    if not url or "dl.moziketo.ir" in url:
        return None
    return url


def resolve_cover_url(_slug: str, stored_url: str | None) -> str | None:
    """Return stored URL only — never synthesize placeholder cover paths."""
    if not stored_url:
        return None
    url = stored_url.strip()
    if not url or "dl.moziketo.ir" in url:
        return None
    return url


def extract_wp_media(meta: dict | None) -> tuple[str | None, str | None, int | None]:
    """Read stream/cover/duration from WordPress station post meta."""
    if not meta:
        return None, None, None
    audio = meta.get("stream_url") or meta.get("download_url")
    if isinstance(audio, str):
        audio = audio.strip() or None
    cover = meta.get("_moziketo_cover_source") or meta.get("cover_url")
    if isinstance(cover, str):
        cover = cover.strip() or None
    duration_raw = meta.get("_moziketo_duration_sec") or meta.get("duration")
    duration: int | None = None
    if duration_raw not in (None, ""):
        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            duration = None
    return audio, cover, duration
