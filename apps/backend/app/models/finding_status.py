"""FindingStatus model — mutable lifecycle state for security findings.

The Finding model is immutable (scanner-produced). FindingStatus tracks
user-initiated lifecycle changes (OPEN → ACKNOWLEDGED → RESOLVED / FALSE_POSITIVE)
in a separate table. This keeps scan results pure and status changes auditable.

Each finding has at most one FindingStatus row. If no row exists, the
finding defaults to OPEN.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FindingStatus(StrEnum):
    """Lifecycle status of a security finding.

    Default is OPEN. Users may transition to ACKNOWLEDGED, RESOLVED,
    or FALSE_POSITIVE. The status is mutable; the Finding itself is not.
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class FindingStatusRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mutable lifecycle status for a security finding.

    One row per finding. If absent, the finding is OPEN.
    """

    __tablename__ = "finding_statuses"

    __table_args__ = (
        UniqueConstraint("finding_id", name="uq_finding_statuses_finding_id"),
        Index("ix_finding_statuses_status", "status"),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[FindingStatus] = mapped_column(
        SAEnum(
            FindingStatus,
            name="finding_status",
            native_enum=False,
            create_constraint=False,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=FindingStatus.OPEN,
        nullable=False,
    )

    # Who set this status (for audit trail).
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    # Optional note (e.g., "acknowledged — will fix in next sprint").
    note: Mapped[str | None] = mapped_column(String(1024))

    # Timestamps are inherited from TimestampMixin (created_at, updated_at).
