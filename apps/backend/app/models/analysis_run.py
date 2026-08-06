"""AnalysisRun aggregate — the execution record of one analysis pipeline run.

Owned by the `analysis` domain (Sprint 4A). The table keeps the *history* of
runs per repository (one repository → many runs); the repository row keeps
only the *latest* lifecycle state (`analysis_status`, `last_analysis_at`,
`last_analysis_job_id`) so nothing is duplicated. Scan findings stay on
future scanner-owned tables (Sprint 5) — this record only tracks the run's
lifecycle, timing and outcome.

The model lives in `app/models/` (not the domain folder) because `app/models/`
is the single schema source Alembic autogenerates from (see
docs/backend-structure.md and docs/adr/0006-analysis-status.md).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class AnalysisRunStatus(StrEnum):
    """Lifecycle of a single analysis run.

    Distinct from the repository-level `AnalysisStatus` (the *latest* state):
    this enum tracks one run from creation to its terminal state. Values are
    the canonical API/DB representation (lowercase snake_case), stored as a
    plain VARCHAR (no CHECK constraint), so new states are code-only additions.
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One analysis pipeline execution for a repository."""

    __tablename__ = "analysis_runs"

    __table_args__ = (
        # DB-level guard against duplicate active runs: the orchestrator's
        # check-then-insert would otherwise let two concurrent starts both
        # pass and insert two QUEUED rows. The filtered unique index makes
        # the second insert fail at the database (both dialects support
        # partial indexes); the orchestrator converts that IntegrityError
        # into the 409 contract.
        Index(
            "uq_analysis_runs_active_repository",
            "repository_id",
            unique=True,
            postgresql_where=sa_text("status IN ('queued', 'running')"),
            sqlite_where=sa_text("status IN ('queued', 'running')"),
        ),
    )

    # ── Scope ───────────────────────────────────────────────────────────
    # Ownership is derived through the repository row (run → repository →
    # owner); `repositories` rows are always owner-scoped.
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Declared relationship so the unit of work inserts the repository row
    # first on FK-enforcing dialects (same fix as Repository.owner).
    repository: Mapped["Repository"] = relationship()

    # ── Lifecycle ───────────────────────────────────────────────────────
    # Who requested the run: "user" today; future automation (Renovate,
    # scheduled pipelines, system) sets its own value.
    triggered_by: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    status: Mapped[AnalysisRunStatus] = mapped_column(
        SAEnum(
            AnalysisRunStatus,
            name="analysis_run_status",
            native_enum=False,
            create_constraint=False,
            length=16,
            # Store the lowercase enum *values* (not member names) — matches
            # the migration's server_default and the API wire format.
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=AnalysisRunStatus.QUEUED,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Whole-run wall-clock time (completed_at - started_at), set on terminal.
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # ── Pipeline identity & outcome ─────────────────────────────────────
    # Version of the analysis pipeline that executed (providers bump this).
    analysis_version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    # Human-readable reason for a failed run (truncated at 512 chars).
    failure_reason: Mapped[str | None] = mapped_column(String(512))
