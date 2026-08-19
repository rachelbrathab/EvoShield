"""ScannerRun — per-scanner execution record within an AnalysisRun.

Sprint 5C.1 introduces multi-scanner orchestration.  A single ``AnalysisRun``
may contain multiple ``ScannerRun`` rows — one per configured scanner
(Trivy, Gitleaks, Semgrep, Syft, Grype).  Each ``ScannerRun`` tracks its
own lifecycle, timing and outcome independently.

The aggregate rule:

    AnalysisRun  1 ──▶ * ScannerRun

An ``AnalysisRun`` completes when all its ``ScannerRun`` rows reach a
terminal state (COMPLETED, FAILED, SKIPPED, or CANCELLED).  The
orchestration layer derives the ``AnalysisRun`` status from the
``ScannerRun`` aggregate — this model is pure data.

Scanner names are stored as plain ``VARCHAR`` (not a DB enum) so new
scanners are added code-only without a migration — the same pattern
used for ``AnalysisStatus`` and ``AnalysisRunStatus``.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScannerRunStatus(StrEnum):
    """Lifecycle of a single scanner execution within an AnalysisRun.

    Stored as VARCHAR — new states are code-only additions.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ScannerRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One scanner's execution within an analysis pipeline run."""

    __tablename__ = "scanner_runs"

    # NOTE: The partial unique index uq_scanner_runs_active_per_analysis
    # is defined only in the Alembic migration (0007), not here, because
    # SQLAlchemy's create_all does not support partial indexes and the
    # drop_all/create_all cycle in tests would fail.  The orchestrator's
    # IntegrityError handling enforces the constraint at the application
    # level.
    # Indexes are defined via index=True on the columns below.

    # ── Scope ───────────────────────────────────────────────────────────
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── Scanner identity ────────────────────────────────────────────────
    # Plain VARCHAR — adding a new scanner is code-only, no migration.
    scanner_name: Mapped[str] = mapped_column(String(32), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Lifecycle ───────────────────────────────────────────────────────
    status: Mapped[ScannerRunStatus] = mapped_column(
        SAEnum(
            ScannerRunStatus,
            name="scanner_run_status",
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=ScannerRunStatus.PENDING,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # ── Outcome ─────────────────────────────────────────────────────────
    finding_count: Mapped[int | None] = mapped_column(Integer)
    component_count: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(String(512))
