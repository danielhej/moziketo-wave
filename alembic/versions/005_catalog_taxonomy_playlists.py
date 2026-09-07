"""Catalog taxonomy, playlists, stream_count

Revision ID: 005
Revises: 004
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("stream_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_tracks_stream_count", "tracks", ["stream_count"], unique=False)

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", "kind", name="uq_tags_slug_kind"),
    )
    op.create_index("ix_tags_kind", "tags", ["kind"], unique=False)

    op.create_table(
        "track_tags",
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("track_id", "tag_id"),
    )

    op.create_table(
        "playlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("cover_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_playlists_slug"),
    )
    op.create_index("ix_playlists_kind", "playlists", ["kind"], unique=False)
    op.create_index("ix_playlists_user_id", "playlists", ["user_id"], unique=False)

    op.create_table(
        "playlist_tracks",
        sa.Column("playlist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playlist_id", "track_id"),
    )
    op.create_index(
        "ix_playlist_tracks_playlist_position",
        "playlist_tracks",
        ["playlist_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_playlist_tracks_playlist_position", table_name="playlist_tracks")
    op.drop_table("playlist_tracks")
    op.drop_index("ix_playlists_user_id", table_name="playlists")
    op.drop_index("ix_playlists_kind", table_name="playlists")
    op.drop_table("playlists")
    op.drop_table("track_tags")
    op.drop_index("ix_tags_kind", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_tracks_stream_count", table_name="tracks")
    op.drop_column("tracks", "stream_count")
