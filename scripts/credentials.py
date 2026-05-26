#!/usr/bin/env python3
"""Olympus credential management using macOS Keychain.

Manages OAuth tokens, API keys, and service credentials securely.
Replaces plaintext tokens in ~/.hermes/ with Keychain entries.

Usage:
    python3 scripts/credentials.py set <service> <key> <value>
    python3 scripts/credentials.py get <service> <key>
    python3 scripts/credentials.py delete <service> <key>
    python3 scripts/credentials.py list [service]
    python3 scripts/credentials.py migrate
"""

from __future__ import annotations

import json
import subprocess
import sys
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


def credential_set(service: str, key: str, value: str) -> bool:
    """Store a credential in macOS Keychain."""
    account = f"{service}:{key}"
    rc, _, stderr = _run_security([
        "add-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", account,
        "-w", value,
        "-U",  # Update if exists
    ])
    if rc != 0:
        print(f"Error storing credential: {stderr.strip()}", file=sys.stderr)
        return False
    return True


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


def credential_delete(service: str, key: str) -> bool:
    """Delete a credential from macOS Keychain."""
    account = f"{service}:{key}"
    rc, _, stderr = _run_security([
        "delete-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", account,
    ])
    if rc != 0:
        print(f"Error deleting credential: {stderr.strip()}", file=sys.stderr)
        return False
    return True


def credential_list(service: Optional[str] = None) -> list[tuple[str, str]]:
    """List all credentials, optionally filtered by service."""
    rc, stdout, stderr = _run_security([
        "dump-keychain",
        "-d",
    ])
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


def migrate_from_env() -> dict[str, bool]:
    """Migrate credentials from ~/.hermes/.env to Keychain.

    Identifies known credential patterns and moves them to Keychain.
    Returns dict of {credential_name: success}.
    """
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        print("No .env file found at ~/.hermes/.env")
        return {}

    # Known credential patterns to migrate
    CREDENTIAL_PATTERNS = {
        "homeassistant": ["HASS_TOKEN", "MCP_HOMEASSISTANT_API_KEY"],
        "withings": ["WITHINGS_CLIENT_ID", "WITHINGS_CLIENT_SECRET"],
        "google": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
    }

    results = {}
    env_content = env_path.read_text()

    for line in env_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not value:
            continue

        # Find which service this belongs to
        for service, patterns in CREDENTIAL_PATTERNS.items():
            if key in patterns:
                success = credential_set(service, key, value)
                results[f"{service}:{key}"] = success
                if success:
                    print(f"  ✓ Migrated {key} to Keychain")
                else:
                    print(f"  ✗ Failed to migrate {key}")

    return results


def migrate_token_files() -> dict[str, bool]:
    """Migrate OAuth token files to Keychain."""
    token_files = {
        "google": Path.home() / ".hermes" / "google" / "token.json",
        "withings": Path.home() / ".hermes" / "withings" / "token.json",
    }

    results = {}
    for service, token_path in token_files.items():
        if not token_path.exists():
            continue

        try:
            tokens = json.loads(token_path.read_text())
            for key, value in tokens.items():
                if key in ("access_token", "refresh_token", "client_id", "client_secret"):
                    success = credential_set(service, key, str(value))
                    results[f"{service}:{key}"] = success
                    if success:
                        print(f"  ✓ Migrated {service}:{key} to Keychain")
        except (json.JSONDecodeError, IOError) as e:
            print(f"  ✗ Error reading {token_path}: {e}")

    return results


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "set":
        if len(sys.argv) < 5:
            print("Usage: credentials.py set <service> <key> <value>")
            sys.exit(1)
        success = credential_set(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0 if success else 1)

    elif command == "get":
        if len(sys.argv) < 4:
            print("Usage: credentials.py get <service> <key>")
            sys.exit(1)
        value = credential_get(sys.argv[2], sys.argv[3])
        if value:
            print(value)
        else:
            print(f"Credential not found: {sys.argv[2]}:{sys.argv[3]}", file=sys.stderr)
            sys.exit(1)

    elif command == "delete":
        if len(sys.argv) < 4:
            print("Usage: credentials.py delete <service> <key>")
            sys.exit(1)
        success = credential_delete(sys.argv[2], sys.argv[3])
        sys.exit(0 if success else 1)

    elif command == "list":
        service = sys.argv[2] if len(sys.argv) > 2 else None
        credentials = credential_list(service)
        if credentials:
            print(f"Credentials{' for ' + service if service else ''}:")
            for svc, key in credentials:
                print(f"  {svc}:{key}")
        else:
            print("No credentials found")

    elif command == "migrate":
        print("Migrating credentials from .env and token files to Keychain...")
        print("\n.env migration:")
        env_results = migrate_from_env()
        print("\nToken file migration:")
        token_results = migrate_token_files()

        total = len(env_results) + len(token_results)
        success = sum(1 for v in (*env_results.values(), *token_results.values()) if v)
        print(f"\nMigration complete: {success}/{total} credentials migrated")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
