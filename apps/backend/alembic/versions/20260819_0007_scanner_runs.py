"""scanner_runs table — per-scanner execution tracking (Sprint 5C.1).

Adds the ``scanner_runs`` table: one row per scanner within an
``AnalysisRun``.  An AnalysisRun may contain multiple ScannerRuns
(Trivy, Gitleaks, Semgrep, Syft, Grype).  Each ScannerRun tracks its
own lifecycle, timing and outcome independently.

Revision ID: 0007
Create Date: 2026-08-19
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the scanner_run_status enum type (VARCHAR, not native enum)
    scanner_run_status_enum = sa.Enum(
        "pending",
        "running",
        "completed",
        "failed",
        "skipped",
        "cancelled",
        name="scanner_run_status",
        native_enum=False,
        length=16,
    )
    scanner_run_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "scanner_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
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
        # ── Scope ───────────────────────────────────────────────────────
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ── Scanner identity ────────────────────────────────────────────
        sa.Column("scanner_name", sa.String(32), nullable=False),
        sa.Column("scanner_version", sa.String(32), nullable=False),
        # ── Lifecycle ───────────────────────────────────────────────────
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        # ── Outcome ─────────────────────────────────────────────────────
        sa.Column("finding_count", sa.Integer(), nullable=True),
        sa.Column("component_count", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.String(512), nullable=True),
    )

    # Indexes
    op.create_index("ix_scanner_runs_analysis_run_id", "scanner_runs", ["analysis_run_id"])
    op.create_index("ix_scanner_runs_status", "scanner_runs", ["status"])

    # Partial unique index: one active (pending/running) run per scanner per analysis.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_scanner_runs_active_per_analysis
        ON scanner_runs (analysis_run_id, scanner_name)
        WHERE status IN ('pending', 'running')
        """
    )


def downgrade() -> None:
    op.drop_table("scanner_runs")
    # Drop the enum type
    sa.Enum(name="scanner_run_status").drop(op.get_bind(), checkfirst=True)
