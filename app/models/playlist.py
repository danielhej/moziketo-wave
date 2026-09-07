from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.user import User


class PlaylistKind:
    EDITORIAL = "editorial"
    USER = "user"


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    playlist: Mapped[Playlist] = relationship(back_populates="playlist_tracks")
    track: Mapped[Track] = relationship(lazy="joined")


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User | None] = relationship(back_populates="playlists", lazy="joined")
    playlist_tracks: Mapped[list[PlaylistTrack]] = relationship(
        back_populates="playlist",
        lazy="selectin",
        order_by="PlaylistTrack.position",
        cascade="all, delete-orphan",
    )
