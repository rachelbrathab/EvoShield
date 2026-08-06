"""Provider access tokens — per-user credentials for upstream integrations.

Sprint 3A: GitHub OAuth exchanges a code for an access token; that token is
what lets EvoShield call the GitHub API *as the user* (list, import, sync
repositories). The identity domain persists it during the OAuth callback;
the `github` domain reads it through shared data access
(`app/repositories/provider_token.py`).

One row per (user, provider) — a unique constraint, not a `users` column, so
GitLab/Bitbucket/Azure DevOps tokens slot in later without a `users` schema
change. Tokens are stored as plain text in dev; production deployments must
encrypt at rest (Supabase column encryption or a KMS-backed envelope) — see
docs/adr/0007-github-integration.md.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class ProviderToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stored access token for one upstream provider, for one user."""

    __tablename__ = "provider_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_provider_tokens_user_provider"),
    )

    # Declared relationship (not a bare FK) so the unit of work inserts the
    # owner `users` row first on FK-enforcing dialects — see the identical
    # fix on `Repository.owner` and `AuthCredential.user`.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user: Mapped["User"] = relationship()

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # SECURITY: plain text in dev only. Production must encrypt at rest
    # (Supabase column encryption / KMS envelope) — Sprint 12 hardening.
    # See docs/adr/0007-github-integration.md.
    access_token: Mapped[str] = mapped_column(String(512), nullable=False)
    token_type: Mapped[str] = mapped_column(String(32), default="bearer", nullable=False)
    scope: Mapped[str | None] = mapped_column(String(512))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
