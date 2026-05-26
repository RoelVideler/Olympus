# plugins/iaso/skills/withings_auth.py
"""OAuth2 token management for Withings API.

Handles token loading, expiry checking, and automatic refresh.
Token stored at ~/.hermes/withings/token.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import httpx

TOKEN_PATH = Path.home() / ".hermes" / "withings" / "token.json"
OAUTH_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"


def load_token() -> Optional[dict]:
    """Load OAuth2 token from disk."""
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text())
    except Exception:
        return None


def save_token(token_data: dict) -> None:
    """Save OAuth2 token to disk."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token_data, indent=2))


def get_access_token() -> Optional[str]:
    """Get a valid access token, refreshing if necessary."""
    token = load_token()
    if not token:
        return None

    # Check if token is expired (with 5 min buffer)
    if token.get("expires_at", 0) < time.time() + 300:
        token = refresh_token(token.get("refresh_token"))
        if not token:
            return None

    return token.get("access_token")


def refresh_token(refresh_token: str) -> Optional[dict]:
    """Refresh an expired OAuth2 token."""
    token = load_token()
    if not token:
        return None

    client_id = token.get("client_id")
    client_secret = token.get("client_secret")
    if not client_id or not client_secret:
        return None

    try:
        response = httpx.post(OAUTH_TOKEN_URL, data={
            "action": "requesttoken",
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, timeout=10)

        if response.status_code != 200:
            return None

        body = response.json().get("body", {})
        if not body.get("access_token"):
            return None

        new_token = {
            **token,
            "access_token": body["access_token"],
            "refresh_token": body.get("refresh_token", refresh_token),
            "expires_at": int(time.time()) + body.get("expires_in", 10800),
        }
        save_token(new_token)
        return new_token
    except Exception:
        return None


def get_userid() -> Optional[str]:
    """Get the Withings user ID from the stored token."""
    token = load_token()
    return token.get("userid") if token else None
