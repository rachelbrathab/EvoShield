"""Identity domain composition — provider auto-selection.

Follows the data-layer precedent (ADR 0001): Supabase when configured,
otherwise the zero-dependency local provider. Selection is logged so the
runtime mode is never ambiguous.
"""

import logging

from app.core.config import get_settings
from app.domains.identity.github_oauth import GitHubOAuthClient
from app.domains.identity.local_provider import LocalAuthProvider
from app.domains.identity.service import IdentityService
from app.domains.identity.supabase_provider import SupabaseAuthProvider

logger = logging.getLogger(__name__)


def build_identity_service() -> IdentityService:
    settings = get_settings()
    mode = (settings.auth_provider or "auto").lower()

    if mode == "supabase" or (
        mode == "auto" and settings.supabase_url and settings.supabase_jwt_secret
    ):
        provider: SupabaseAuthProvider | LocalAuthProvider = SupabaseAuthProvider()
        logger.info("Auth provider: Supabase (mode=%s)", mode)
    else:
        provider = LocalAuthProvider()
        logger.warning(
            "Auth provider: LOCAL (mode=%s). Supabase credentials not configured — "
            "this fallback must never be enabled in production.",
            mode,
        )

    return IdentityService(provider=provider, github=GitHubOAuthClient())
