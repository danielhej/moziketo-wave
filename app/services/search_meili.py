from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.catalog import ArtistSummary, SearchResponse, TrackSummary


def meili_available() -> bool:
    settings = get_settings()
    return bool(settings.meili_url.strip() and settings.meili_api_key.strip())


def meili_search_enabled() -> bool:
    settings = get_settings()
    return meili_available() and settings.search_backend == "meili"


def meili_configured() -> bool:
    """Backward-compatible alias for search path."""
    return meili_search_enabled()


def _index_name(kind: str) -> str:
    settings = get_settings()
    prefix = settings.meili_index_prefix.strip() or "moziketo"
    return f"{prefix}_{kind}"


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.meili_api_key:
        headers["Authorization"] = f"Bearer {settings.meili_api_key}"
    return headers


async def ensure_indexes() -> None:
    if not meili_available():
        return
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.meili_url.rstrip("/"), timeout=30) as client:
        for kind, searchable, filterable in (
            ("tracks", ["title", "artist_name", "slug"], ["published"]),
            ("artists", ["name", "name_en", "slug"], []),
            ("albums", ["title", "artist_name", "slug"], ["published"]),
        ):
            index_uid = _index_name(kind)
            await client.post(
                f"/indexes/{index_uid}/settings/searchable-attributes",
                headers=_headers(),
                json=searchable,
            )
            if filterable:
                await client.post(
                    f"/indexes/{index_uid}/settings/filterable-attributes",
                    headers=_headers(),
                    json=filterable,
                )


async def upsert_documents(kind: str, documents: list[dict[str, Any]]) -> None:
    if not meili_available() or not documents:
        return
    settings = get_settings()
    index_uid = _index_name(kind)
    async with httpx.AsyncClient(base_url=settings.meili_url.rstrip("/"), timeout=60) as client:
        await client.post(
            f"/indexes/{index_uid}/documents",
            headers=_headers(),
            json=documents,
        )


async def delete_document(kind: str, doc_id: str) -> None:
    if not meili_available():
        return
    settings = get_settings()
    index_uid = _index_name(kind)
    async with httpx.AsyncClient(base_url=settings.meili_url.rstrip("/"), timeout=30) as client:
        await client.delete(f"/indexes/{index_uid}/documents/{doc_id}", headers=_headers())


async def search_meili(*, q: str, limit: int) -> SearchResponse | None:
    if not meili_search_enabled():
        return None
    settings = get_settings()
    query = q.strip()
    async with httpx.AsyncClient(base_url=settings.meili_url.rstrip("/"), timeout=30) as client:
        track_resp = await client.post(
            f"/indexes/{_index_name('tracks')}/search",
            headers=_headers(),
            json={"q": query, "limit": limit, "filter": "published = true"},
        )
        artist_resp = await client.post(
            f"/indexes/{_index_name('artists')}/search",
            headers=_headers(),
            json={"q": query, "limit": limit},
        )

    if track_resp.status_code >= 400 or artist_resp.status_code >= 400:
        return None

    track_hits = track_resp.json().get("hits", [])
    artist_hits = artist_resp.json().get("hits", [])

    tracks = [
        TrackSummary(
            id=str(hit["id"]),
            slug=hit["slug"],
            title=hit["title"],
            artist_name=hit.get("artist_name", ""),
            duration_seconds=hit.get("duration_seconds"),
            cover_url=hit.get("cover_url"),
            stream_count=hit.get("stream_count", 0),
        )
        for hit in track_hits
    ]
    artists = [
        ArtistSummary(
            id=str(hit["id"]),
            slug=hit["slug"],
            name=hit["name"],
            name_en=hit.get("name_en"),
            cover_url=hit.get("cover_url"),
            track_count=int(hit.get("track_count", 0)),
        )
        for hit in artist_hits
    ]
    return SearchResponse(
        query=query,
        tracks=tracks,
        artists=artists,
        track_total=track_resp.json().get("estimatedTotalHits", len(tracks)),
        artist_total=artist_resp.json().get("estimatedTotalHits", len(artists)),
    )
