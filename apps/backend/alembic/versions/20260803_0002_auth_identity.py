"""auth identity: provider columns + local credentials table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03

Sprint 2 — authentication. Adds the identity linkage columns to `users`
and the `auth_credentials` table used by the local auth provider (dev
fallback). Supabase-backed deployments never populate `auth_credentials`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=32),
            server_default="local",
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("auth_provider_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_auth_provider_sub", "users", ["auth_provider_sub"])

    op.create_table(
        "auth_credentials",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("auth_credentials")
    op.drop_index("ix_users_auth_provider_sub", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "auth_provider_sub")
    op.drop_column("users", "auth_provider")
