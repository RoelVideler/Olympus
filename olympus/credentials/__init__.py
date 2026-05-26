"""Credential management module for Olympus plugins.

Provides transparent credential access with Keychain priority,
falling back to environment variables and token files.

Usage in plugins:
    from olympus.credentials import get_credential

    # Get a credential (tries Keychain → env → token file)
    token = get_credential("google", "access_token")

    # Set a credential (stores in Keychain)
    set_credential("google", "access_token", "new_token_value")
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

KEYCHAIN_SERVICE = "Olympus"


def _run_security(args: list[str]) -> tuple[int, str, str]:
    """Run security command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["security"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def credential_get(service: str, key: str) -> Optional[str]:
    """Retrieve a credential from macOS Keychain."""
    account = f"{service}:{key}"
    rc, stdout, stderr = _run_security([
        "find-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", account,
        "-w",
    ])
    if rc != 0:
        return None
    return stdout.strip()


def credential_set(service: str, key: str, value: str) -> bool:
    """Store a credential in macOS Keychain."""
    account = f"{service}:{key}"
    rc, _, stderr = _run_security([
        "add-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", account,
        "-w", value,
        "-U",
    ])
    return rc == 0


def credential_delete(service: str, key: str) -> bool:
    """Delete a credential from macOS Keychain."""
    account = f"{service}:{key}"
    rc, _, stderr = _run_security([
        "delete-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", account,
    ])
    return rc == 0


def credential_list(service: Optional[str] = None) -> list[tuple[str, str]]:
    """List all credentials, optionally filtered by service."""
    rc, stdout, stderr = _run_security(["dump-keychain", "-d"])
    if rc != 0:
        return []

    credentials = []
    current_service = None
    current_account = None

    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith('"svce"'):
            current_service = line.split('"')[-2]
        elif line.startswith('"acct"'):
            current_account = line.split('"')[-2]
        elif line == "}" and current_service == KEYCHAIN_SERVICE and current_account:
            if ":" in current_account:
                svc, key = current_account.split(":", 1)
                if service is None or svc == service:
                    credentials.append((svc, key))
            current_account = None

    return credentials


def get_credential(service: str, key: str) -> Optional[str]:
    """Get a credential with fallback chain: Keychain → env → token file."""
    # 1. Try Keychain
    value = credential_get(service, key)
    if value:
        return value

    # 2. Try environment variable
    env_patterns = [
        f"HERMES_{service.upper()}_{key.upper()}",
        f"{service.upper()}_{key.upper()}",
        f"HERMES_{key.upper()}",
        key.upper(),
    ]
    for pattern in env_patterns:
        value = os.environ.get(pattern)
        if value:
            return value

    # 3. Try token file
    token_path = Path.home() / ".hermes" / service / "token.json"
    if token_path.exists():
        try:
            tokens = json.loads(token_path.read_text())
            value = tokens.get(key)
            if value:
                return str(value)
        except (json.JSONDecodeError, IOError):
            pass

    # 4. Try .env file
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        try:
            env_content = env_path.read_text()
            for line in env_content.split("\n"):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip().upper() in [
                    f"{service.upper()}_{key.upper()}",
                    key.upper(),
                    f"HERMES_{key.upper()}",
                ]:
                    return env_value.strip()
        except IOError:
            pass

    return None


def set_credential(service: str, key: str, value: str) -> bool:
    """Set a credential in Keychain."""
    return credential_set(service, key, value)


def delete_credential(service: str, key: str) -> bool:
    """Delete a credential from Keychain."""
    return credential_delete(service, key)


def list_credentials(service: Optional[str] = None) -> list[tuple[str, str]]:
    """List all stored credentials."""
    return credential_list(service)
