"""Local-provider credentials.

The local auth provider (dev fallback) stores password hashes here, keeping
authentication data out of the application `users` profile table — the same
separation Supabase has between `auth.users` and public profiles. Supabase
projects never use this table.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuthCredential(Base):
    """Password hash for a local-provider account."""

    __tablename__ = "auth_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Declared relationship (not just a bare FK) so the unit of work orders
    # the parent `users` INSERT before this child row on every dialect.
    # Without it, INSERT order falls back to mapper sort order and Postgres
    # rejects the FK (SQLite never notices: foreign keys are off by default).
    user: Mapped["User"] = relationship()
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
