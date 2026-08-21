"""0008_finding_statuses — mutable lifecycle status for security findings.

Revision ID: 48c42ca6936c
Revises: 0007
Create Date: 2026-08-21 15:29:53.200214+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48c42ca6936c"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finding_statuses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "finding_id",
            sa.Uuid(),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "set_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("finding_id", name="uq_finding_statuses_finding_id"),
        sa.Index("ix_finding_statuses_finding_id", "finding_id"),
        sa.Index("ix_finding_statuses_status", "status"),
        sa.Index("ix_finding_statuses_set_by_user_id", "set_by_user_id"),
    )


def downgrade() -> None:
    op.drop_table("finding_statuses")
