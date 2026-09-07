from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import track_tags

if TYPE_CHECKING:
    from app.models.artist import Artist
    from app.models.playlist import PlaylistTrack
    from app.models.tag import Tag


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), index=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stream_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    artist: Mapped[Artist] = relationship(back_populates="tracks", lazy="joined")
    tags: Mapped[list[Tag]] = relationship(
        secondary=track_tags,
        back_populates="tracks",
        lazy="selectin",
    )
    playlist_tracks: Mapped[list[PlaylistTrack]] = relationship(
        lazy="selectin",
        viewonly=True,
        overlaps="track",
    )
