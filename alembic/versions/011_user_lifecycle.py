"""User lifecycle fields

Revision ID: 011
Revises: 010
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("pending_email", sa.String(length=320), nullable=True))
    op.add_column(
        "users", sa.Column("email_change_token_hash", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "email_change_token_hash")
    op.drop_column("users", "pending_email")
    op.drop_column("users", "deleted_at")
