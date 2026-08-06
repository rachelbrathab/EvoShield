"""provider tokens + repository github metadata

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-06

Sprint 3A — repository integration platform. Two schema changes:

1. `provider_tokens`: per-user upstream access tokens (GitHub now; GitLab,
   Bitbucket, Azure DevOps later). Written by the identity domain during the
   GitHub OAuth callback, read by the `github` domain to call the GitHub API
   as the user. `UNIQUE (user_id, provider)` — one token per provider.

2. `repositories`: GitHub metadata columns the import/sync services populate
   (language, stars, forks, open_issues, topics, license, size, archived,
   disabled, upstream timestamps, `last_synced_at`). All nullable or
   server-defaulted, so existing rows and the `RepositoryRead` contract stay
   backward compatible. No scan data — that stays on future scanner tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("access_token", sa.String(length=512), nullable=False),
        sa.Column(
            "token_type",
            sa.String(length=32),
            server_default="bearer",
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_tokens_user_provider"),
    )
    op.create_index("ix_provider_tokens_user_id", "provider_tokens", ["user_id"])
    op.create_index("ix_provider_tokens_provider", "provider_tokens", ["provider"])

    # Repository metadata (Sprint 3A) — all additive.
    op.add_column("repositories", sa.Column("language", sa.String(length=64), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("stars", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("forks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("open_issues", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("topics", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column("repositories", sa.Column("license", sa.String(length=128), nullable=True))
    op.add_column("repositories", sa.Column("size_kb", sa.BigInteger(), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_repositories_pushed_at", "repositories", ["pushed_at"])


def downgrade() -> None:
    op.drop_index("ix_repositories_pushed_at", table_name="repositories")
    op.drop_column("repositories", "last_synced_at")
    op.drop_column("repositories", "pushed_at")
    op.drop_column("repositories", "provider_updated_at")
    op.drop_column("repositories", "provider_created_at")
    op.drop_column("repositories", "disabled")
    op.drop_column("repositories", "archived")
    op.drop_column("repositories", "size_kb")
    op.drop_column("repositories", "license")
    op.drop_column("repositories", "topics")
    op.drop_column("repositories", "open_issues")
    op.drop_column("repositories", "forks")
    op.drop_column("repositories", "stars")
    op.drop_column("repositories", "language")

    op.drop_index("ix_provider_tokens_provider", table_name="provider_tokens")
    op.drop_index("ix_provider_tokens_user_id", table_name="provider_tokens")
    op.drop_table("provider_tokens")
