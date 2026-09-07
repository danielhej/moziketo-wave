from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import track_tags

if TYPE_CHECKING:
    from app.models.track import Track


class TagKind:
    GENRE = "genre"
    MOOD = "mood"
    STATION_TAG = "station_tag"


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("slug", "kind", name="uq_tags_slug_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tracks: Mapped[list[Track]] = relationship(
        secondary=track_tags,
        back_populates="tags",
        lazy="selectin",
    )
