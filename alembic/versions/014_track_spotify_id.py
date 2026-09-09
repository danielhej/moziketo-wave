"""Add spotify_id to tracks for unified search/stream keys."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("spotify_id", sa.String(length=32), nullable=True))
    op.create_index("ix_tracks_spotify_id", "tracks", ["spotify_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tracks_spotify_id", table_name="tracks")
    op.drop_column("tracks", "spotify_id")
