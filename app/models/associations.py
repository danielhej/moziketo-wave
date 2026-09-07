from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

track_tags = Table(
    "track_tags",
    Base.metadata,
    Column(
        "track_id",
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
