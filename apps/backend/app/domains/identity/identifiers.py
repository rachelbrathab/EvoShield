"""Deterministic user-id mapping across auth providers.

Provider subjects are not all UUIDs: GitHub user IDs are integers
(e.g. "583231"), while Supabase and the local provider use UUIDs. The
`users.id` column is a UUID, so non-UUID subjects must be mapped to a
*stable* UUID — same provider subject always yields the same application
user id, which is what makes re-authentication idempotent.
"""

import uuid

# Fixed namespace so generated ids are stable across processes and
# deployments (do not change; it would orphan existing GitHub users).
_PROVIDER_NAMESPACE = uuid.UUID("6e76efd3-4a10-4c7f-8c2b-2a6c9f1d0e33")


def resolve_user_id(provider: str, provider_sub: str) -> uuid.UUID:
    """Map a provider subject to the application user UUID.

    UUID-shaped subjects pass through unchanged; anything else (numeric
    GitHub ids, legacy formats) is hashed into a deterministic UUID via
    the provider namespace.
    """
    try:
        return uuid.UUID(str(provider_sub))
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(_PROVIDER_NAMESPACE, f"{provider}:{provider_sub}")
