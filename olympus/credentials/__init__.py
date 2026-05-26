"""Credential management module for Olympus plugins.

Provides transparent credential access with Vaultwarden priority,
falling back to environment variables and token files.

Usage in plugins:
    from olympus.credentials import get_credential

    # Get a credential (tries Vaultwarden → env → token file)
    token = get_credential("google", "access_token")

    # Set a credential (stores in Vaultwarden)
    set_credential("google", "access_token", "new_token_value")
"""

from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Configuration
VAULTWARDEN_URL = os.environ.get("VAULTWARDEN_URL", "https://192.168.1.10:7277")
VAULTWARDEN_CLIENT_ID = os.environ.get("VAULTWARDEN_CLIENT_ID", "user.16ac75bc-dbbb-492d-a0a3-f2600eb8ccc2")
VAULTWARDEN_CLIENT_SECRET = os.environ.get("VAULTWARDEN_CLIENT_SECRET", "2PqZnLMUt8PJq9U5ufvesDYGsA2m9n")
VAULT_FOLDER_ID = "5fc7b2d8-981b-4daa-9748-f1d26e165df6"

# Session token cache
_session_token = None


def _get_ssl_context():
    """Create SSL context that ignores certificate verification."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


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

    with urlopen(req, context=_get_ssl_context()) as resp:
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

    with urlopen(req, context=_get_ssl_context()) as resp:
        content = resp.read()
        if not content:
            return {}
        return json.loads(content)


def _find_item(service: str, key: str) -> Optional[dict]:
    """Find a vault item by service and key."""
    items = _vault_request("/api/ciphers")["data"]
    for item in items:
        if item.get("folderId") != VAULT_FOLDER_ID:
            continue
        name = item.get("name", "")
        if name.lower() == service.lower():
            login = item.get("login", {})
            if login.get("username") == key:
                return item
            for field in item.get("fields", []):
                if field.get("name") == key:
                    return item
    return None


def credential_get(service: str, key: str) -> Optional[str]:
    """Retrieve a credential from Vaultwarden."""
    try:
        item = _find_item(service, key)
        if not item:
            return None

        login = item.get("login", {})
        if login.get("username") == key:
            return login.get("password")

        for field in item.get("fields", []):
            if field.get("name") == key:
                return field.get("value")

        return None
    except Exception:
        return None


def credential_set(service: str, key: str, value: str) -> bool:
    """Store a credential in Vaultwarden."""
    try:
        item = _find_item(service, key)

        if item:
            item_id = item["id"]
            login = item.get("login", {})
            login["username"] = key
            login["password"] = value

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
            body = {
                "folderId": VAULT_FOLDER_ID,
                "type": 1,
                "name": service,
                "login": {"username": key, "password": value},
                "fields": [{"name": key, "value": value, "type": 1}],
            }

            _vault_request("/api/ciphers", method="POST", body=body)

        return True
    except Exception:
        return False


def credential_delete(service: str, key: str) -> bool:
    """Delete a credential from Vaultwarden."""
    try:
        item = _find_item(service, key)
        if not item:
            return False

        _vault_request(f"/api/ciphers/{item['id']}", method="DELETE")
        return True
    except Exception:
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


def get_credential(service: str, key: str) -> Optional[str]:
    """Get a credential with fallback chain: Vaultwarden → env → token file."""
    # 1. Try Vaultwarden
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
    """Set a credential in Vaultwarden."""
    return credential_set(service, key, value)


def delete_credential(service: str, key: str) -> bool:
    """Delete a credential from Vaultwarden."""
    return credential_delete(service, key)


def list_credentials(service: Optional[str] = None) -> list[tuple[str, str]]:
    """List all stored credentials."""
    return credential_list(service)
