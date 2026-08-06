"""Application user record.

The auth provider (Supabase in production, the local provider in dev) owns
*authentication*; this table is the application-side profile. The id mirrors
the auth identity UUID, and `auth_provider_sub` keeps the provider's subject
identifier (e.g. the GitHub user id) so provider identities map cleanly.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An EvoShield user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Auth identity linkage.
    auth_provider: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    auth_provider_sub: Mapped[str | None] = mapped_column(String(255), index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
