"""Unit tests for provider-subject → user-id resolution."""

import uuid

from app.domains.identity.identifiers import resolve_user_id


def test_uuid_subject_passes_through() -> None:
    subject = "3f2e6b8a-9c1d-4e5f-8a7b-0c1d2e3f4a5b"
    assert resolve_user_id("local", subject) == uuid.UUID(subject)


def test_numeric_github_subject_maps_to_stable_uuid() -> None:
    first = resolve_user_id("github", "583231")
    second = resolve_user_id("github", "583231")
    assert isinstance(first, uuid.UUID)
    # Deterministic: same subject always yields the same application id.
    assert first == second


def test_different_subjects_map_to_different_uuids() -> None:
    a = resolve_user_id("github", "111")
    b = resolve_user_id("github", "222")
    assert a != b


def test_provider_is_part_of_the_namespace() -> None:
    # Same numeric subject under different providers must not collide.
    github_id = resolve_user_id("github", "42")
    local_id = resolve_user_id("local", "42")
    assert github_id != local_id
