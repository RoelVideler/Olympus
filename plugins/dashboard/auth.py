"""Session cookie authentication for the Dashboard plugin.

Uses HttpOnly, SameSite=Strict cookies with a locally-generated secret
for signing. Middleware rejects unauthenticated requests with 401.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)

COOKIE_NAME = "olympus_session"
SESSION_TTL_SECONDS = 86400  # 24 hours


def _generate_secret() -> bytes:
    """Generate or retrieve a persistent session signing secret."""
    secret_path = os.path.expanduser("~/.hermes/.dashboard_secret")
    os.makedirs(os.path.dirname(secret_path), exist_ok=True)

    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read()

    secret = secrets.token_bytes(32)
    with open(secret_path, "wb") as f:
        f.write(secret)
    os.chmod(secret_path, 0o600)
    return secret


_SECRET = _generate_secret()


def _sign(payload: str) -> str:
    """Sign a payload with HMAC-SHA256."""
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify(cookie_value: str) -> Optional[str]:
    """Verify a signed cookie and return the payload, or None if invalid."""
    try:
        parts = cookie_value.rsplit(".", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts
        expected = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return payload
    except Exception:
        return None


def create_session(user_id: str = "admin") -> str:
    """Create a signed session cookie value."""
    payload = json.dumps({"user": user_id, "ts": time.time()})
    return _sign(payload)


def is_session_valid(cookie_value: str) -> bool:
    """Check if a session cookie is valid and not expired."""
    payload = _verify(cookie_value)
    if payload is None:
        return False
    try:
        data = json.loads(payload)
        age = time.time() - data.get("ts", 0)
        return age < SESSION_TTL_SECONDS
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


@web.middleware
async def auth_middleware(request: web.Request, handler: Callable) -> web.Response:
    """Authentication middleware that rejects unauthenticated requests."""
    # Allow login endpoint through
    if request.path == "/api/login":
        return await handler(request)

    # Allow health check without auth
    if request.path == "/api/health" and request.method == "HEAD":
        return await handler(request)

    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie or not is_session_valid(cookie):
        return web.json_response(
            {"error": "Unauthorized", "message": "Valid session cookie required"},
            status=401,
        )

    return await handler(request)


def set_session_cookie(response: web.Response, user_id: str = "admin") -> None:
    """Set a session cookie on a response."""
    cookie_value = create_session(user_id)
    response.set_cookie(
        COOKIE_NAME,
        cookie_value,
        httponly=True,
        samesite="Strict",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


async def handle_login(request: web.Request) -> web.Response:
    """Login endpoint — creates a session cookie."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # Simple single-user auth — accept any non-empty password for local use
    password = body.get("password", "")
    if not password:
        return web.json_response({"error": "Password required"}, status=400)

    # Check against stored password hash (or create one on first login)
    password_hash_path = os.path.expanduser("~/.hermes/.dashboard_password")
    if os.path.exists(password_hash_path):
        with open(password_hash_path, "r") as f:
            stored_hash = f.read().strip()
        if hashlib.sha256(password.encode()).hexdigest() != stored_hash:
            return web.json_response({"error": "Invalid password"}, status=401)
    else:
        # First login — store the password hash
        os.makedirs(os.path.dirname(password_hash_path), exist_ok=True)
        with open(password_hash_path, "w") as f:
            f.write(hashlib.sha256(password.encode()).hexdigest())
        os.chmod(password_hash_path, 0o600)
        logger.info("Dashboard password set for first time")

    response = web.json_response({"ok": True, "message": "Logged in"})
    set_session_cookie(response)
    return response
