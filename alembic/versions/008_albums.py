"""Albums and track.album_id

Revision ID: 008
Revises: 007
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "albums",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("artist_id", sa.UUID(), nullable=False),
        sa.Column("cover_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_albums_artist_id"), "albums", ["artist_id"], unique=False)
    op.create_index(op.f("ix_albums_slug"), "albums", ["slug"], unique=True)

    op.add_column("tracks", sa.Column("album_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_tracks_album_id"), "tracks", ["album_id"], unique=False)
    op.create_foreign_key(
        "fk_tracks_album_id_albums",
        "tracks",
        "albums",
        ["album_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tracks_album_id_albums", "tracks", type_="foreignkey")
    op.drop_index(op.f("ix_tracks_album_id"), table_name="tracks")
    op.drop_column("tracks", "album_id")
    op.drop_index(op.f("ix_albums_slug"), table_name="albums")
    op.drop_index(op.f("ix_albums_artist_id"), table_name="albums")
    op.drop_table("albums")
