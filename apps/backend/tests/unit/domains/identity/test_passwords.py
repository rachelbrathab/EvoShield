"""Unit tests for password hashing (Argon2id via pwdlib)."""

from app.domains.identity.passwords import hash_password, verify_password


def test_hash_verify_roundtrip() -> None:
    digest = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", digest)


def test_wrong_password_rejected() -> None:
    digest = hash_password("right-password")
    assert not verify_password("wrong-password", digest)


def test_hashes_are_salted_and_unique() -> None:
    # Same input must never produce the same digest (unique per-password salt).
    assert hash_password("same-password") != hash_password("same-password")


def test_hash_format_is_argon2id() -> None:
    digest = hash_password("whatever")
    # pwdlib recommended() = Argon2id; encoded hashes start with the argon2 prefix.
    assert digest.startswith("$argon2")
