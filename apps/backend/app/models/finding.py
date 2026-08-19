"""Finding model — normalized security findings from any scanner.

One `AnalysisRun` can produce many findings.  The `findings` table stores
scanner-agnostic normalized data — no Trivy-specific, Syft-specific, or
Semgrep-specific columns.  Each scanner maps its native output onto these
universal fields (see `app/domains/scanners/ports.py` for the contract).

The enum columns (`severity`, `finding_type`) use the same VARCHAR pattern
as `AnalysisStatus` and `AnalysisRunStatus`: `native_enum=False`,
`create_constraint=False`, `validate_strings=True`.  New values are
code-only additions — no migration required.
"""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis_run import AnalysisRun


class Severity(StrEnum):
    """Normalized severity of a security finding."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingType(StrEnum):
    """Category of security finding."""

    VULNERABILITY = "vulnerability"
    SECRET = "secret"
    SAST = "sast"
    LICENSE = "license"
    CONFIGURATION = "configuration"
    SBOM = "sbom"


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single normalized security finding from a scanner."""

    __tablename__ = "findings"

    __table_args__ = (
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_finding_type", "finding_type"),
        Index("ix_findings_vulnerability_id", "vulnerability_id"),
    )

    # ── Scope ───────────────────────────────────────────────────────────
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    analysis_run: Mapped["AnalysisRun"] = relationship()

    # ── Scanner identity ────────────────────────────────────────────────
    scanner: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scanner_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Finding classification ──────────────────────────────────────────
    finding_type: Mapped[FindingType] = mapped_column(
        SAEnum(
            FindingType,
            name="finding_type",
            native_enum=False,
            create_constraint=False,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    severity: Mapped[Severity] = mapped_column(
        SAEnum(
            Severity,
            name="finding_severity",
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=False,
    )

    # ── Finding details ─────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048))

    # ── Package / dependency info ───────────────────────────────────────
    package_name: Mapped[str | None] = mapped_column(String(256))
    installed_version: Mapped[str | None] = mapped_column(String(128))
    fixed_version: Mapped[str | None] = mapped_column(String(128))

    # ── Vulnerability reference ─────────────────────────────────────────
    vulnerability_id: Mapped[str | None] = mapped_column(String(64))
    references_json: Mapped[str | None] = mapped_column(String(4096))

    # ── Location ────────────────────────────────────────────────────────
    location: Mapped[str | None] = mapped_column(String(1024))
