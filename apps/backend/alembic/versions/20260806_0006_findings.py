"""findings table — normalized security scan results.

Sprint 5A.  One AnalysisRun produces many Findings.  The table stores
scanner-agnostic normalized data: severity, finding_type (enum-as-VARCHAR),
package info, vulnerability references, and location.  No scanner-specific
columns.

Revision ID: 0006
Create Date: 2026-08-19
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the finding_severity enum type (VARCHAR, not native enum)
    finding_severity_enum = sa.Enum(
        "unknown",
        "low",
        "medium",
        "high",
        "critical",
        name="finding_severity",
        native_enum=False,
        length=16,
    )
    finding_severity_enum.create(op.get_bind(), checkfirst=True)

    # Create the finding_type enum type (VARCHAR, not native enum)
    finding_type_enum = sa.Enum(
        "vulnerability",
        "secret",
        "sast",
        "license",
        "configuration",
        "sbom",
        name="finding_type",
        native_enum=False,
        length=32,
    )
    finding_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("scanner", sa.String(32), nullable=False, index=True),
        sa.Column("scanner_version", sa.String(32), nullable=False),
        sa.Column(
            "finding_type",
            finding_type_enum,
            nullable=False,
        ),
        sa.Column(
            "severity",
            finding_severity_enum,
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.String(2048), nullable=True),
        sa.Column("package_name", sa.String(256), nullable=True),
        sa.Column("installed_version", sa.String(128), nullable=True),
        sa.Column("fixed_version", sa.String(128), nullable=True),
        sa.Column("vulnerability_id", sa.String(64), nullable=True),
        sa.Column("references_json", sa.String(4096), nullable=True),
        sa.Column("location", sa.String(1024), nullable=True),
    )

    # Additional indexes for common queries
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_finding_type", "findings", ["finding_type"])
    op.create_index("ix_findings_vulnerability_id", "findings", ["vulnerability_id"])


def downgrade() -> None:
    op.drop_table("findings")
    sa.Enum(name="finding_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="finding_severity").drop(op.get_bind(), checkfirst=True)
