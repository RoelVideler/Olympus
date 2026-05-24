"""Phase 2 REST endpoints for the Dashboard plugin.

Serves data from the shared SQLite database:
- GET /api/health — health data
- GET /api/wiki — wiki data
- GET /api/calendar — calendar data
- GET /api/contacts — contacts data
- GET /api/preferences — preferences data
- Deferred endpoints return 501 Not Implemented
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.hermes/olympus.db")

DEFERRED_ENDPOINTS = {
    "/api/notifications",
    "/api/tasks",
    "/api/messages",
    "/api/files",
    "/api/notes",
    "/api/bookmarks",
    "/api/search",
    "/api/analytics",
}


def get_db() -> sqlite3.Connection:
    """Get a connection to the shared SQLite database."""
    if not os.path.exists(DB_PATH):
        logger.warning("Database not found at %s — returning empty results", DB_PATH)
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dict(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Convert sqlite3.Row objects to dictionaries."""
    return [dict(row) for row in rows]


async def handle_health(request: web.Request) -> web.Response:
    """GET /api/health — return system health data."""
    conn = get_db()
    if conn is None:
        return web.json_response({
            "status": "ok",
            "database": "not_found",
            "profiles": [],
        })

    try:
        # Get profile statuses
        cursor = conn.execute(
            "SELECT name, status, run_mode FROM agent_profiles ORDER BY name"
        )
        profiles = _rows_to_dict(cursor.fetchall())

        # Get knowledge stats
        cursor = conn.execute(
            "SELECT scope, COUNT(*) as count FROM olympus_knowledge GROUP BY scope"
        )
        knowledge_stats = _rows_to_dict(cursor.fetchall())

        return web.json_response({
            "status": "ok",
            "database": "connected",
            "profiles": profiles,
            "knowledge_stats": knowledge_stats,
        })
    except sqlite3.Error as e:
        logger.error("Health query failed: %s", e)
        return web.json_response({
            "status": "error",
            "database": "query_failed",
            "error": str(e),
        }, status=500)
    finally:
        conn.close()


async def handle_wiki(request: web.Request) -> web.Response:
    """GET /api/wiki — return wiki data."""
    conn = get_db()
    if conn is None:
        return web.json_response({"wiki_entries": []})

    try:
        domain = request.query.get("domain")
        scope = request.query.get("scope")

        query = "SELECT * FROM olympus_knowledge WHERE 1=1"
        params: list = []

        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if scope:
            query += " AND scope = ?"
            params.append(scope)

        query += " ORDER BY updated_at DESC"

        cursor = conn.execute(query, params)
        entries = _rows_to_dict(cursor.fetchall())

        return web.json_response({"wiki_entries": entries})
    except sqlite3.Error as e:
        logger.error("Wiki query failed: %s", e)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_calendar(request: web.Request) -> web.Response:
    """GET /api/calendar — return calendar data."""
    # Calendar table may not exist yet — return empty
    conn = get_db()
    if conn is None:
        return web.json_response({"events": []})

    try:
        # Check if calendar table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'"
        )
        if not cursor.fetchone():
            return web.json_response({"events": [], "note": "calendar table not yet created"})

        cursor = conn.execute(
            "SELECT * FROM calendar_events ORDER BY start_time ASC"
        )
        events = _rows_to_dict(cursor.fetchall())

        return web.json_response({"events": events})
    except sqlite3.Error as e:
        logger.error("Calendar query failed: %s", e)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_contacts(request: web.Request) -> web.Response:
    """GET /api/contacts — return contacts data."""
    conn = get_db()
    if conn is None:
        return web.json_response({"contacts": []})

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
        )
        if not cursor.fetchone():
            return web.json_response({"contacts": [], "note": "contacts table not yet created"})

        cursor = conn.execute("SELECT * FROM contacts ORDER BY name ASC")
        contacts = _rows_to_dict(cursor.fetchall())

        return web.json_response({"contacts": contacts})
    except sqlite3.Error as e:
        logger.error("Contacts query failed: %s", e)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_preferences(request: web.Request) -> web.Response:
    """GET /api/preferences — return preferences data."""
    conn = get_db()
    if conn is None:
        return web.json_response({"preferences": {}})

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='preferences'"
        )
        if not cursor.fetchone():
            return web.json_response({"preferences": {}, "note": "preferences table not yet created"})

        cursor = conn.execute("SELECT key, value FROM preferences")
        prefs = {row["key"]: row["value"] for row in cursor.fetchall()}

        return web.json_response({"preferences": prefs})
    except sqlite3.Error as e:
        logger.error("Preferences query failed: %s", e)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_not_implemented(request: web.Request) -> web.Response:
    """Return 501 for deferred endpoints."""
    return web.json_response(
        {"error": "Not Implemented", "message": f"{request.path} is planned for Phase 3+"},
        status=501,
    )


def register_routes(app: web.Application) -> None:
    """Register all REST routes on the aiohttp application."""
    # Phase 2 endpoints
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/wiki", handle_wiki)
    app.router.add_get("/api/calendar", handle_calendar)
    app.router.add_get("/api/contacts", handle_contacts)
    app.router.add_get("/api/preferences", handle_preferences)

    # Login endpoint (no auth required)
    from .auth import handle_login
    app.router.add_post("/api/login", handle_login)

    # Deferred endpoints
    for path in DEFERRED_ENDPOINTS:
        app.router.add_get(path, handle_not_implemented)
