"""Session token hashing and server-side token encryption."""

from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fernet_from_settings_key(raw_key: str) -> Fernet:
    # Accept a real Fernet key, or derive one for local development placeholders.
    try:
        return Fernet(raw_key.encode("utf-8"))
    except (ValueError, TypeError):
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(raw_key: str, plaintext: str) -> str:
    token = _fernet_from_settings_key(raw_key).encrypt(plaintext.encode("utf-8"))
    return str(token.decode("utf-8"))


def decrypt_secret(raw_key: str, ciphertext: str) -> str:
    try:
        plain = _fernet_from_settings_key(raw_key).decrypt(ciphertext.encode("utf-8"))
        return str(plain.decode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret") from exc
