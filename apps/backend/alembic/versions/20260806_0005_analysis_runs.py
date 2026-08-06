"""analysis runs table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-06

Sprint 4A — analysis infrastructure. Creates `analysis_runs`, the execution
history of the analysis pipeline (one repository → many runs). It tracks only
the run lifecycle (status, timing, version, failure reason) — no findings or
vulnerabilities yet; those belong to scanner-owned tables in Sprint 5. The
repository row keeps its existing `analysis_status` / `last_analysis_at` /
`last_analysis_job_id` as the *latest* state, so the two stay in sync via the
orchestrator.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_by", sa.String(length=32), server_default="user", nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "analysis_version",
            sa.String(length=32),
            server_default="0.1.0",
            nullable=False,
        ),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
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
    )
    op.create_index("ix_analysis_runs_repository_id", "analysis_runs", ["repository_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    # Filtered unique index: at most one active (queued/running) run per
    # repository — the DB-level half of the duplicate-active-run 409.
    op.create_index(
        "uq_analysis_runs_active_repository",
        "analysis_runs",
        ["repository_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_runs_active_repository", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_status", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_repository_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
