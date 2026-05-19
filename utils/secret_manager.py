"""Secret loading helpers for deployment.

This module intentionally keeps the interface small. It supports three sources,
in priority order:

1. Direct environment variable, for local development.
2. File pointed to by <NAME>_FILE, for Docker/systemd secrets.
3. Encrypted JSON file pointed to by STF_ENCRYPTED_SECRETS_FILE.

The encrypted file is decrypted with a Fernet key from STF_SECRETS_KEY or
STF_SECRETS_KEY_FILE. This protects secrets at rest and from accidental git
leaks; it does not protect against an attacker with full access to the running
process or the decryption key.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


class SecretManagerError(RuntimeError):
    """Raised when a configured secret source cannot be read."""


def get_secret(name: str, *, required: bool = True) -> str | None:
    """Return a secret value from env, secret file, or encrypted secrets."""

    value = os.getenv(name)
    if value:
        return value

    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        return _read_secret_file(file_path)

    encrypted_secrets = _load_encrypted_secrets()
    value = encrypted_secrets.get(name)
    if isinstance(value, str) and value:
        return value

    if required:
        raise SecretManagerError(
            f"Secret {name} is required. Set {name}, {name}_FILE, or configure STF_ENCRYPTED_SECRETS_FILE."
        )
    return None


def get_openai_api_key() -> str:
    """Return the OpenAI API key used by OpenAI SDK clients."""

    return get_secret("OPENAI_KEY")


def _read_secret_file(file_path: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SecretManagerError(f"Unable to read secret file {file_path}: {exc}") from exc


@lru_cache(maxsize=1)
def _load_encrypted_secrets() -> dict[str, Any]:
    encrypted_file = os.getenv("STF_ENCRYPTED_SECRETS_FILE")
    if not encrypted_file:
        return {}

    key = _load_secrets_key()
    try:
        encrypted_payload = Path(encrypted_file).read_bytes()
        decrypted_payload = _decrypt_fernet(encrypted_payload, key)
        parsed = json.loads(decrypted_payload.decode("utf-8"))
    except OSError as exc:
        raise SecretManagerError(f"Unable to read encrypted secrets file {encrypted_file}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SecretManagerError(f"Encrypted secrets file {encrypted_file} does not contain JSON.") from exc

    if not isinstance(parsed, dict):
        raise SecretManagerError(f"Encrypted secrets file {encrypted_file} must decrypt to a JSON object.")
    return parsed


def _load_secrets_key() -> str:
    key = os.getenv("STF_SECRETS_KEY")
    if key:
        return key.strip()

    key_file = os.getenv("STF_SECRETS_KEY_FILE")
    if key_file:
        return _read_secret_file(key_file)

    raise SecretManagerError("STF_SECRETS_KEY or STF_SECRETS_KEY_FILE is required for encrypted secrets.")


def _decrypt_fernet(encrypted_payload: bytes, key: str) -> bytes:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError as exc:
        raise SecretManagerError("Install the cryptography package to use encrypted secrets.") from exc

    try:
        return Fernet(key.encode("utf-8")).decrypt(encrypted_payload)
    except InvalidToken as exc:
        raise SecretManagerError("Unable to decrypt encrypted secrets. Check STF_SECRETS_KEY.") from exc
