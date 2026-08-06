"""Repository aggregate and its analysis-status enum.

The `repositories` table is the persistence foundation for Sprint 3 (GitHub
ingestion) and the analysis pipeline (Sprint 4+). It carries exactly one
*current* analysis state per repository (`analysis_status` plus the timestamp
and job id of the most recent run); full per-run *history* belongs to a future
`analysis_runs` table owned by the `analysis` domain, so nothing is duplicated.

Scan-specific data (SBOMs, findings, vulnerabilities) deliberately does **not**
live on this table — scanners get their own tables in Sprint 5, and the
pipeline only ever flips `analysis_status` on the repository row.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisStatus(StrEnum):
    """Lifecycle state of a repository's most recent analysis run.

    Values are the canonical API/DB representation (lowercase snake_case).
    New states can be added by appending a member here: the column stores a
    plain VARCHAR (no database CHECK constraint), so no migration is required.
    """

    NOT_ANALYZED = "not_analyzed"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Repository(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A source repository tracked by EvoShield.

    Provider-agnostic on purpose: `provider` + `provider_repo_id` identify the
    upstream (GitHub, and later GitLab/Bitbucket/Azure DevOps), while the
    human-facing `full_name` ("owner/name") is the natural key per user.
    """

    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("owner_id", "full_name", name="uq_repositories_owner_full_name"),
    )

    # ── Ownership & source identity ─────────────────────────────────────
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), default="github", index=True, nullable=False)
    # Upstream's own id (e.g. GitHub's numeric repository id); populated by
    # Sprint 3 ingestion. Kept as string so numeric and non-numeric ids fit.
    provider_repo_id: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    html_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(String(1024))
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Analysis status (Sprint 4+ pipeline writes these) ───────────────
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(
            AnalysisStatus,
            name="analysis_status",
            native_enum=False,
            create_constraint=False,
            length=32,
            # Store the lowercase enum *values* (not the member names), so DB
            # values match the migration's server_default and the API wire
            # format. validate_strings rejects free-form strings at the model
            # boundary — not just at the Pydantic contract layer.
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=AnalysisStatus.NOT_ANALYZED,
        index=True,
        nullable=False,
    )
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Opaque id of the most recent analysis job (worker/queue job id).
    last_analysis_job_id: Mapped[str | None] = mapped_column(String(64))
