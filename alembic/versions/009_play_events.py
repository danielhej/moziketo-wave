"""Play events for listening history

Revision ID: 009
Revises: 008
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "play_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.UUID(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "played_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_play_events_track_id"), "play_events", ["track_id"], unique=False)
    op.create_index(op.f("ix_play_events_user_id"), "play_events", ["user_id"], unique=False)
    op.create_index(
        "ix_play_events_user_played_at",
        "play_events",
        ["user_id", sa.text("played_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_play_events_user_played_at", table_name="play_events")
    op.drop_index(op.f("ix_play_events_user_id"), table_name="play_events")
    op.drop_index(op.f("ix_play_events_track_id"), table_name="play_events")
    op.drop_table("play_events")
