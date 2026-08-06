"""repository table with first-class analysis status

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-06

Sprint 3 preparation — introduces the `repositories` table carrying the
analysis-status trio (`analysis_status`, `last_analysis_at`,
`last_analysis_job_id`). Sprint 4/5 pipelines update only these columns;
scan-specific data (SBOMs, findings, vulnerabilities) gets its own tables so
the repository row stays normalized and provider-agnostic.

`analysis_status` is a plain VARCHAR (native_enum=False, no CHECK constraint)
so new enum states can be added in code without a schema migration — see
docs/adr/0006-analysis-status.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="github",
            nullable=False,
        ),
        sa.Column("provider_repo_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("html_url", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column(
            "is_private",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "analysis_status",
            sa.Enum(
                "not_analyzed",
                "queued",
                "analyzing",
                "analyzed",
                "failed",
                "cancelled",
                name="analysis_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="not_analyzed",
            nullable=False,
        ),
        sa.Column("last_analysis_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_analysis_job_id", sa.String(length=64), nullable=True),
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
        sa.UniqueConstraint(
            "owner_id", "full_name", name="uq_repositories_owner_full_name"
        ),
    )
    op.create_index("ix_repositories_owner_id", "repositories", ["owner_id"])
    op.create_index("ix_repositories_provider", "repositories", ["provider"])
    op.create_index(
        "ix_repositories_provider_repo_id", "repositories", ["provider_repo_id"]
    )
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
    op.create_index(
        "ix_repositories_analysis_status", "repositories", ["analysis_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_repositories_analysis_status", table_name="repositories")
    op.drop_index("ix_repositories_full_name", table_name="repositories")
    op.drop_index("ix_repositories_provider_repo_id", table_name="repositories")
    op.drop_index("ix_repositories_provider", table_name="repositories")
    op.drop_index("ix_repositories_owner_id", table_name="repositories")
    op.drop_table("repositories")
