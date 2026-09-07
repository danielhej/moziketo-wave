from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Tag, TagKind, Track
from app.schemas import TagListResponse, TagSummary, TagTrackListResponse
from app.services.cache import cache_get, cache_set
from app.services.catalog import _apply_track_filters, _track_order, _track_summary
from app.services.media import published_track_filter


async def _tag_track_count(session: AsyncSession, tag_id) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Track)
            .join(Track.tags)
            .where(Tag.id == tag_id)
            .where(published_track_filter())
        )
        or 0
    )


async def list_tags_by_kind(session: AsyncSession, kind: str) -> TagListResponse:
    cache_key = f"tags:{kind}:list"
    cached = await cache_get(cache_key)
    if cached is not None:
        return TagListResponse.model_validate(cached)

    result = await session.execute(select(Tag).where(Tag.kind == kind).order_by(Tag.name))
    tags = result.scalars().all()

    items: list[TagSummary] = []
    for tag in tags:
        count = await _tag_track_count(session, tag.id)
        if count == 0:
            continue
        items.append(
            TagSummary(
                id=str(tag.id),
                slug=tag.slug,
                name=tag.name,
                kind=tag.kind,
                track_count=count,
            )
        )

    response = TagListResponse(items=items, total=len(items))
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response


async def list_tracks_for_tag(
    session: AsyncSession,
    *,
    kind: str,
    slug: str,
    page: int = 1,
    page_size: int = 24,
) -> TagTrackListResponse:
    cache_key = f"tags:{kind}:{slug}:tracks:{page}:{page_size}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return TagTrackListResponse.model_validate(cached)

    tag = await session.scalar(select(Tag).where(Tag.kind == kind, Tag.slug == slug))
    if tag is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * page_size

    filter_kwargs = {"genre": slug if kind == TagKind.GENRE else None}
    if kind == TagKind.MOOD:
        filter_kwargs = {"mood": slug}
    elif kind == TagKind.STATION_TAG:
        filter_kwargs = {"tag": slug}

    count_stmt = select(func.count()).select_from(Track).where(published_track_filter())
    count_stmt = _apply_track_filters(count_stmt, **filter_kwargs)
    total = await session.scalar(count_stmt) or 0

    stmt = (
        select(Track)
        .options(selectinload(Track.artist))
        .where(published_track_filter())
    )
    stmt = _apply_track_filters(stmt, **filter_kwargs)
    stmt = stmt.order_by(*_track_order("latest")).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    tracks = result.scalars().unique().all()

    track_count = await _tag_track_count(session, tag.id)
    tag_summary = TagSummary(
        id=str(tag.id),
        slug=tag.slug,
        name=tag.name,
        kind=tag.kind,
        track_count=track_count,
    )
    response = TagTrackListResponse(
        tag=tag_summary,
        items=[_track_summary(t) for t in tracks],
        total=total,
        page=page,
        page_size=page_size,
    )
    await cache_set(cache_key, response.model_dump(mode="json"))
    return response
