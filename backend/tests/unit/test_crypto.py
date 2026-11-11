"""Session hashing and encryption tests."""

from __future__ import annotations

from stockpilot.platform.security.crypto import (
    decrypt_secret,
    encrypt_secret,
    hash_token,
    new_token,
)


def test_hash_is_stable_and_not_raw() -> None:
    raw = new_token()
    assert hash_token(raw) != raw
    assert hash_token(raw) == hash_token(raw)


def test_encrypt_roundtrip() -> None:
    key = "dev-only-fernet-key-32bytes-long!!"
    token = "refresh-token-value"
    encrypted = encrypt_secret(key, token)
    assert encrypted != token
    assert decrypt_secret(key, encrypted) == token
