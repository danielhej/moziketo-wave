"""pg_trgm search indexes

Revision ID: 004
Revises: 003
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tracks_title_trgm ON tracks "
        "USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_artists_name_trgm ON artists "
        "USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_artists_name_en_trgm ON artists "
        "USING gin (name_en gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_artists_name_en_trgm")
    op.execute("DROP INDEX IF EXISTS ix_artists_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_tracks_title_trgm")
