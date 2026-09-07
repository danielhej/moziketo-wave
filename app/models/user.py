from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.favorite import Favorite
    from app.models.oauth_account import OAuthAccount
    from app.models.play_event import PlayEvent
    from app.models.playlist import Playlist


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    favorites: Mapped[list[Favorite]] = relationship(back_populates="user", lazy="selectin")
    playlists: Mapped[list[Playlist]] = relationship(back_populates="user", lazy="selectin")
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        back_populates="user", lazy="selectin"
    )
    play_events: Mapped[list[PlayEvent]] = relationship(back_populates="user", lazy="raise")
