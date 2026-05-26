#!/usr/bin/env python3
"""Olympus credential management using Vaultwarden.

Manages OAuth tokens, API keys, and service credentials securely.
Replaces plaintext tokens in ~/.hermes/ with Vaultwarden entries.

Usage:
    python3 scripts/credentials.py set <service> <key> <value>
    python3 scripts/credentials.py get <service> <key>
    python3 scripts/credentials.py delete <service> <key>
    python3 scripts/credentials.py list [service]
    python3 scripts/credentials.py migrate
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Configuration
VAULTWARDEN_URL = os.environ.get("VAULTWARDEN_URL", "https://192.168.1.10:7277")
VAULTWARDEN_CLIENT_ID = os.environ.get("VAULTWARDEN_CLIENT_ID", "user.16ac75bc-dbbb-492d-a0a3-f2600eb8ccc2")
VAULTWARDEN_CLIENT_SECRET = os.environ.get("VAULTWARDEN_CLIENT_SECRET", "2PqZnLMUt8PJq9U5ufvesDYGsA2m9n")
VAULT_FOLDER_NAME = "Olympus"
VAULT_FOLDER_ID = "5fc7b2d8-981b-4daa-9748-f1d26e165df6"

# Session token cache
_session_token = None


def _get_access_token() -> str:
    """Get Vaultwarden access token, refreshing if needed."""
    global _session_token
    if _session_token:
        return _session_token

    data = urlencode({
        "grant_type": "client_credentials",
        "client_id": VAULTWARDEN_CLIENT_ID,
        "client_secret": VAULTWARDEN_CLIENT_SECRET,
        "scope": "api",
        "device_identifier": "olympus-hermes",
        "device_name": "Olympus Hermes",
        "device_type": "10",
    }).encode()

    req = Request(
        f"{VAULTWARDEN_URL}/identity/connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Disable SSL verification for self-signed certs
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urlopen(req, context=ctx) as resp:
        tokens = json.loads(resp.read())

    _session_token = tokens["access_token"]
    return _session_token


def _vault_request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """Make an authenticated request to Vaultwarden."""
    token = _get_access_token()
    url = f"{VAULTWARDEN_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None

    req = Request(url, data=data, headers=headers, method=method)

    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urlopen(req, context=ctx) as resp:
        return json.loads(resp.read())


def _find_item(service: str, key: str) -> Optional[dict]:
    """Find a vault item by service and key."""
    items = _vault_request("/api/ciphers")["data"]
    for item in items:
        if item.get("folderId") != VAULT_FOLDER_ID:
            continue
        name = item.get("name", "")
        if name.lower() == service.lower():
            # Check if this item has the key
            login = item.get("login", {})
            if login.get("username") == key:
                return item
            # Check custom fields
            for field in item.get("fields", []):
                if field.get("name") == key:
                    return item
    return None


def credential_set(service: str, key: str, value: str) -> bool:
    """Store a credential in Vaultwarden."""
    try:
        # Check if item exists
        item = _find_item(service, key)

        if item:
            # Update existing item
            item_id = item["id"]
            login = item.get("login", {})
            login["username"] = key
            login["password"] = value

            # Update custom field if exists
            fields = item.get("fields", [])
            field_updated = False
            for field in fields:
                if field.get("name") == key:
                    field["value"] = value
                    field_updated = True
                    break

            if not field_updated:
                fields.append({"name": key, "value": value, "type": 1})

            body = {
                "id": item_id,
                "folderId": VAULT_FOLDER_ID,
                "type": 1,
                "name": service,
                "login": login,
                "fields": fields,
            }

            _vault_request(f"/api/ciphers/{item_id}", method="PUT", body=body)
        else:
            # Create new item
            body = {
                "folderId": VAULT_FOLDER_ID,
                "type": 1,
                "name": service,
                "login": {
                    "username": key,
                    "password": value,
                },
                "fields": [{"name": key, "value": value, "type": 1}],
            }

            _vault_request("/api/ciphers", method="POST", body=body)

        return True
    except Exception as e:
        print(f"Error storing credential: {e}", file=sys.stderr)
        return False


def credential_get(service: str, key: str) -> Optional[str]:
    """Retrieve a credential from Vaultwarden."""
    try:
        item = _find_item(service, key)
        if not item:
            return None

        # Check login password first
        login = item.get("login", {})
        if login.get("username") == key:
            return login.get("password")

        # Check custom fields
        for field in item.get("fields", []):
            if field.get("name") == key:
                return field.get("value")

        return None
    except Exception:
        return None


def credential_delete(service: str, key: str) -> bool:
    """Delete a credential from Vaultwarden."""
    try:
        item = _find_item(service, key)
        if not item:
            return False

        item_id = item["id"]
        _vault_request(f"/api/ciphers/{item_id}", method="DELETE")
        return True
    except Exception as e:
        print(f"Error deleting credential: {e}", file=sys.stderr)
        return False


def credential_list(service: Optional[str] = None) -> list[tuple[str, str]]:
    """List all credentials, optionally filtered by service."""
    try:
        items = _vault_request("/api/ciphers")["data"]
        credentials = []
        for item in items:
            if item.get("folderId") != VAULT_FOLDER_ID:
                continue
            name = item.get("name", "")
            if service and name.lower() != service.lower():
                continue

            login = item.get("login", {})
            if login.get("username"):
                credentials.append((name, login["username"]))

            for field in item.get("fields", []):
                if field.get("name"):
                    credentials.append((name, field["name"]))

        return credentials
    except Exception:
        return []


def migrate_from_env() -> dict[str, bool]:
    """Migrate credentials from ~/.hermes/.env to Vaultwarden."""
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        print("No .env file found at ~/.hermes/.env")
        return {}

    CREDENTIAL_PATTERNS = {
        "homeassistant": ["HASS_TOKEN", "MCP_HOMEASSISTANT_API_KEY"],
        "withings": ["WITHINGS_CLIENT_ID", "WITHINGS_CLIENT_SECRET"],
        "google": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
    }

    results = {}
    env_content = env_path.read_text()

    for line in env_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not value:
            continue

        for svc, patterns in CREDENTIAL_PATTERNS.items():
            if key in patterns:
                success = credential_set(svc, key, value)
                results[f"{svc}:{key}"] = success
                print(f"  {'✓' if success else '✗'} Migrated {key} to Vaultwarden")

    return results


def migrate_token_files() -> dict[str, bool]:
    """Migrate OAuth token files to Vaultwarden."""
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
                    print(f"  {'✓' if success else '✗'} Migrated {service}:{key} to Vaultwarden")
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
        print("Migrating credentials from .env and token files to Vaultwarden...")
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
