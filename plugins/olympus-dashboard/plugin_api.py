"""Olympus dashboard plugin — FastAPI backend for Hermes dashboard.

Mounted at /api/plugins/olympus/ by the Hermes dashboard plugin system.

Endpoints:
- GET  /health       — system health data
- GET  /wiki         — wiki/knowledge entries
- GET  /calendar     — calendar events
- GET  /contacts     — contact list
- GET  /preferences  — user preferences
- GET  /ws           — WebSocket for real-time streaming
- POST /graphql      — complex multi-type queries
- GET  /tasks        — 501 Not Implemented (deferred)
- ...other deferred endpoints...

Auth: Handled by the Hermes dashboard session middleware. No login endpoint
needed — the dashboard's built-in auth protects all plugin routes.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status as http_status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

DB_PATH = Path.home() / ".hermes" / "olympus.db"

DEFERRED_ENDPOINTS = [
    "/tasks",
    "/notifications",
    "/messages",
    "/files",
    "/notes",
    "/bookmarks",
    "/search",
    "/analytics",
]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db() -> Optional[sqlite3.Connection]:
    """Get a connection to the shared SQLite database."""
    if not DB_PATH.exists():
        logger.warning("Database not found at %s", DB_PATH)
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dict(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Convert sqlite3.Row objects to dictionaries."""
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def get_health():
    """GET /health — return system health data."""
    conn = _get_db()
    if conn is None:
        return {"status": "ok", "database": "not_found", "profiles": []}

    try:
        cursor = conn.execute(
            "SELECT name, status, run_mode FROM agent_profiles ORDER BY name"
        )
        profiles = _rows_to_dict(cursor.fetchall())

        cursor = conn.execute(
            "SELECT scope, COUNT(*) as count FROM olympus_knowledge GROUP BY scope"
        )
        knowledge_stats = _rows_to_dict(cursor.fetchall())

        return {
            "status": "ok",
            "database": "connected",
            "profiles": profiles,
            "knowledge_stats": knowledge_stats,
        }
    except sqlite3.Error as e:
        logger.error("Health query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/wiki")
def get_wiki(
    domain: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
):
    """GET /wiki — return wiki/knowledge entries."""
    conn = _get_db()
    if conn is None:
        return {"wiki_entries": []}

    try:
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

        return {"wiki_entries": entries}
    except sqlite3.Error as e:
        logger.error("Wiki query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/calendar")
def get_calendar():
    """GET /calendar — return calendar events."""
    conn = _get_db()
    if conn is None:
        return {"events": []}

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'"
        )
        if not cursor.fetchone():
            return {"events": []}

        cursor = conn.execute("SELECT * FROM calendar_events ORDER BY start_time ASC")
        events = _rows_to_dict(cursor.fetchall())

        return {"events": events}
    except sqlite3.Error as e:
        logger.error("Calendar query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/contacts")
def get_contacts():
    """GET /contacts — return contact list."""
    conn = _get_db()
    if conn is None:
        return {"contacts": []}

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
        )
        if not cursor.fetchone():
            return {"contacts": []}

        cursor = conn.execute("SELECT * FROM contacts ORDER BY name ASC")
        contacts = _rows_to_dict(cursor.fetchall())

        return {"contacts": contacts}
    except sqlite3.Error as e:
        logger.error("Contacts query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/preferences")
def get_preferences():
    """GET /preferences — return user preferences."""
    conn = _get_db()
    if conn is None:
        return {"preferences": {}}

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='preferences'"
        )
        if not cursor.fetchone():
            return {"preferences": {}}

        cursor = conn.execute("SELECT key, value FROM preferences")
        prefs = {row["key"]: row["value"] for row in cursor.fetchall()}

        return {"preferences": prefs}
    except sqlite3.Error as e:
        logger.error("Preferences query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# Deferred endpoints (501)
for _path in DEFERRED_ENDPOINTS:
    @router.get(_path)
    def not_implemented():
        raise HTTPException(
            status_code=501,
            detail=f"{_path} is planned for Phase 3+",
        )


# ---------------------------------------------------------------------------
# GraphQL endpoint (lightweight string-matching parser)
# ---------------------------------------------------------------------------

def _execute_graphql(query_str: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute a GraphQL-like query against the SQLite database.

    Lightweight fallback that parses simple queries by checking if field
    names appear in the query string. No external GraphQL library needed.
    """
    conn = _get_db()
    if conn is None:
        return {"data": {}, "error": "Database not found"}

    result: Dict[str, Any] = {}
    try:
        if "health" in query_str:
            cursor = conn.execute(
                "SELECT name, status, run_mode FROM agent_profiles ORDER BY name"
            )
            result["health"] = {
                "status": "ok",
                "profiles": _rows_to_dict(cursor.fetchall()),
            }

        if "wiki" in query_str:
            domain = variables.get("domain") if variables else None
            scope = variables.get("scope") if variables else None
            q = "SELECT * FROM olympus_knowledge WHERE 1=1"
            params: list = []
            if domain:
                q += " AND domain = ?"
                params.append(domain)
            if scope:
                q += " AND scope = ?"
                params.append(scope)
            q += " ORDER BY updated_at DESC"
            result["wiki"] = _rows_to_dict(conn.execute(q, params).fetchall())

        if "calendar" in query_str:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'"
            )
            if cursor.fetchone():
                result["calendar"] = _rows_to_dict(
                    conn.execute("SELECT * FROM calendar_events ORDER BY start_time ASC").fetchall()
                )
            else:
                result["calendar"] = []

        if "contacts" in query_str:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
            )
            if cursor.fetchone():
                result["contacts"] = _rows_to_dict(
                    conn.execute("SELECT * FROM contacts ORDER BY name ASC").fetchall()
                )
            else:
                result["contacts"] = []

        if "preferences" in query_str:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='preferences'"
            )
            if cursor.fetchone():
                result["preferences"] = {
                    row["key"]: row["value"]
                    for row in conn.execute("SELECT key, value FROM preferences").fetchall()
                }
            else:
                result["preferences"] = {}

        return {"data": result}
    except Exception as e:
        logger.error("GraphQL query failed: %s", e)
        return {"data": result, "errors": [{"message": str(e)}]}
    finally:
        conn.close()


class GraphqlBody(BaseModel):
    query: str = ""
    variables: Optional[Dict] = None


@router.post("/graphql")
def handle_graphql(body: GraphqlBody):
    """POST /graphql — handle GraphQL queries."""
    if not body.query:
        raise HTTPException(status_code=400, detail="query is required")

    result = _execute_graphql(body.query, body.variables)
    return result


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

# WebSocket auth helper — follows the kanban plugin pattern
def _check_ws_token(provided: Optional[str]) -> bool:
    """Constant-time compare against the dashboard session token."""
    if not provided:
        return False
    try:
        from hermes_cli import web_server as _ws
    except Exception:
        return True  # No dashboard context (tests)
    expected = getattr(_ws, "_SESSION_TOKEN", None)
    if not expected:
        return True
    return hmac.compare_digest(str(provided), str(expected))


class WebSocketHub:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.append(ws)
        logger.info("WebSocket connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections = [c for c in self._connections if c != ws]
        logger.info("WebSocket disconnected (%d total)", len(self._connections))

    async def broadcast(self, event: Dict[str, Any]) -> None:
        message = json.dumps(event)
        async with self._lock:
            dead = []
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections = [c for c in self._connections if c != ws]


_hub: Optional[WebSocketHub] = None


def get_hub() -> WebSocketHub:
    global _hub
    if _hub is None:
        _hub = WebSocketHub()
    return _hub


@router.websocket("/ws")
async def stream_websocket(ws: WebSocket, token: Optional[str] = Query(None)):
    """GET /ws — WebSocket endpoint for real-time streaming."""
    if not _check_ws_token(token):
        await ws.close(code=http_status.WS_1008_POLICY_VIOLATION)
        return

    await ws.accept()

    hub = get_hub()
    await hub.connect(ws)

    await ws.send_json({
        "type": "connected",
        "timestamp": time.time(),
        "message": "Connected to Olympus Dashboard",
    })

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "subscribe":
                    await ws.send_json({
                        "type": "subscribed",
                        "channels": msg.get("channels", ["*"]),
                    })
                elif msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "timestamp": time.time()})
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)


async def stream_zeus_response(session_id: str, chunk: str) -> None:
    """Stream a Zeus response chunk to all connected clients."""
    hub = get_hub()
    await hub.broadcast({
        "type": "zeus_chunk",
        "session_id": session_id,
        "chunk": chunk,
        "timestamp": time.time(),
    })


async def stream_system_event(event_type: str, data: Dict[str, Any]) -> None:
    """Stream a system event to all connected clients."""
    hub = get_hub()
    await hub.broadcast({
        "type": "system_event",
        "event_type": event_type,
        "data": data,
        "timestamp": time.time(),
    })
