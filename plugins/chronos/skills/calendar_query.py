# plugins/chronos/skills/calendar_query.py
"""Google Calendar query tool for Chronos.

Read-only access to Google Calendar via OAuth tokens.
Tokens stored at ~/.hermes/google/token.json with auto-refresh.
Supports: list_calendars, list_events, get_event, free_busy, share_fact.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOKEN_PATH = Path.home() / ".hermes" / "google" / "token.json"
DB_PATH = Path.home() / ".hermes" / "olympus.db"

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

CALENDAR_QUERY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calendar_query",
        "description": "Query Google Calendar for events, calendars, and availability. Read-only.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list_calendars",
                        "list_events",
                        "get_event",
                        "free_busy",
                        "search_events",
                        "share_fact",
                    ],
                    "description": "Action to perform.",
                },
                "calendar_id": {
                    "type": "string",
                    "maxLength": 500,
                    "default": "primary",
                    "description": "Calendar ID (use 'primary' for main calendar).",
                },
                "time_min": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Start time filter (RFC3339, e.g., 2026-05-26T00:00:00+02:00).",
                },
                "time_max": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "End time filter (RFC3339).",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 250,
                    "default": 20,
                    "description": "Maximum events to return.",
                },
                "single_events": {
                    "type": "boolean",
                    "default": True,
                    "description": "Expand recurring events into instances.",
                },
                "order_by": {
                    "type": "string",
                    "enum": ["startTime", "updated"],
                    "default": "startTime",
                    "description": "Sort order for events.",
                },
                "query": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Free text search for events.",
                },
                "event_id": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Event ID for get_event.",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                        },
                    },
                    "description": "Calendar IDs for free_busy query.",
                },
                "fact": {
                    "type": "string",
                    "maxLength": 10000,
                    "description": "Fact to share via share_knowledge (for share_fact action).",
                },
            },
            "required": ["action"],
        },
    },
}


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS calendar_event_cache (
            id TEXT PRIMARY KEY,
            event_id TEXT,
            calendar_id TEXT,
            summary TEXT,
            description TEXT,
            location TEXT,
            start_time TEXT,
            end_time TEXT,
            is_all_day INTEGER DEFAULT 0,
            status TEXT,
            attendees TEXT,
            cached_at TEXT DEFAULT (datetime('now'))
        );
    """)


def _tool_error(message: str, **extra) -> str:
    result = {"error": str(message)}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def _tool_result(data=None, **kwargs) -> str:
    if data is not None:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(kwargs, ensure_ascii=False)


def _load_tokens() -> dict:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"Google OAuth token not found at {TOKEN_PATH}")
    with open(TOKEN_PATH) as f:
        return json.load(f)


def _save_tokens(tokens: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def _refresh_access_token(refresh_token: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data)
    with urllib.request.urlopen(req) as resp:
        new_tokens = json.loads(resp.read())
    new_tokens["refresh_token"] = refresh_token
    return new_tokens


def _get_access_token() -> str:
    tokens = _load_tokens()
    expires_at = tokens.get("expires_at", 0)
    if expires_at and datetime.now().timestamp() > expires_at - 300:
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise ValueError("Token expired and no refresh token available")
        new_tokens = _refresh_access_token(refresh_token)
        new_tokens["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)
        _save_tokens(new_tokens)
        return new_tokens["access_token"]
    return tokens["access_token"]


def _calendar_request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    access_token = _get_access_token()
    url = f"{CALENDAR_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    if body:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            tokens = _load_tokens()
            new_tokens = _refresh_access_token(tokens["refresh_token"])
            new_tokens["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)
            _save_tokens(new_tokens)
            headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        raise


def _format_event(event: dict) -> dict:
    """Format a calendar event for display."""
    start = event.get("start", {})
    end = event.get("end", {})

    is_all_day = "date" in start
    start_time = start.get("dateTime", start.get("date", ""))
    end_time = end.get("dateTime", end.get("date", ""))

    attendees = []
    for att in event.get("attendees", []):
        attendees.append({
            "email": att.get("email", ""),
            "name": att.get("displayName", ""),
            "status": att.get("responseStatus", "needsAction"),
        })

    return {
        "event_id": event.get("id", ""),
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start_time,
        "end": end_time,
        "is_all_day": is_all_day,
        "status": event.get("status", "confirmed"),
        "attendees": attendees,
        "html_link": event.get("htmlLink", ""),
    }


def handle_calendar_query(args: dict, **kw) -> str:
    """Handle calendar_query tool calls."""
    action = str(args.get("action") or "").strip().lower()

    valid_actions = ("list_calendars", "list_events", "get_event", "free_busy", "search_events", "share_fact")
    if action not in valid_actions:
        return _tool_error(f"Unknown action: {action}. Must be one of: {', '.join(valid_actions)}")

    conn = None
    try:
        conn = _get_db()
        _ensure_schema(conn)
    except Exception as e:
        return _tool_error(f"Database connection failed: {e}")

    try:
        if action == "list_calendars":
            return _list_calendars(conn, args)
        elif action == "list_events":
            return _list_events(conn, args)
        elif action == "get_event":
            return _get_event(conn, args)
        elif action == "free_busy":
            return _free_busy(conn, args)
        elif action == "search_events":
            return _search_events(conn, args)
        elif action == "share_fact":
            return _share_fact(args)
    except FileNotFoundError as e:
        return _tool_error(str(e))
    except Exception as e:
        return _tool_error(f"calendar_query failed: {type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()


def _list_calendars(conn: sqlite3.Connection, args: dict) -> str:
    result = _calendar_request("/users/me/calendarList")
    calendars = result.get("items", [])

    formatted = []
    for cal in calendars:
        formatted.append({
            "id": cal.get("id", ""),
            "summary": cal.get("summary", ""),
            "description": cal.get("description", ""),
            "time_zone": cal.get("timeZone", ""),
            "primary": cal.get("primary", False),
            "access_role": cal.get("accessRole", ""),
        })

    return _tool_result({
        "status": "ok",
        "calendars": formatted,
        "count": len(formatted),
    })


def _list_events(conn: sqlite3.Connection, args: dict) -> str:
    calendar_id = args.get("calendar_id", "primary")
    max_results = min(int(args.get("max_results", 20)), 250)
    single_events = args.get("single_events", True)
    order_by = args.get("order_by", "startTime")

    # Default: next 7 days
    now = datetime.now(timezone.utc)
    time_min = args.get("time_min", now.isoformat())
    time_max = args.get("time_max", (now + timedelta(days=7)).isoformat())

    params = urllib.parse.urlencode({
        "maxResults": max_results,
        "singleEvents": str(single_events).lower(),
        "orderBy": order_by,
        "timeMin": time_min,
        "timeMax": time_max,
    })

    result = _calendar_request(f"/calendars/{urllib.parse.quote(calendar_id)}/events?{params}")
    events = result.get("items", [])

    formatted = []
    for event in events:
        if event.get("status") == "cancelled":
            continue
        evt = _format_event(event)
        formatted.append(evt)

        # Cache event
        conn.execute(
            """
            INSERT OR REPLACE INTO calendar_event_cache
            (id, event_id, calendar_id, summary, description, location, start_time, end_time, is_all_day, status, attendees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                event.get("id", ""),
                calendar_id,
                event.get("summary", ""),
                event.get("description", ""),
                event.get("location", ""),
                evt["start"],
                evt["end"],
                1 if evt["is_all_day"] else 0,
                evt["status"],
                json.dumps(evt["attendees"]),
            ),
        )

    conn.commit()

    return _tool_result({
        "status": "ok",
        "calendar_id": calendar_id,
        "events": formatted,
        "count": len(formatted),
        "time_min": time_min,
        "time_max": time_max,
    })


def _get_event(conn: sqlite3.Connection, args: dict) -> str:
    calendar_id = args.get("calendar_id", "primary")
    event_id = args.get("event_id")
    if not event_id:
        return _tool_error("event_id is required for get_event")

    result = _calendar_request(f"/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}")

    evt = _format_event(result)

    # Cache event
    conn.execute(
        """
        INSERT OR REPLACE INTO calendar_event_cache
        (id, event_id, calendar_id, summary, description, location, start_time, end_time, is_all_day, status, attendees)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            result.get("id", ""),
            calendar_id,
            result.get("summary", ""),
            result.get("description", ""),
            result.get("location", ""),
            evt["start"],
            evt["end"],
            1 if evt["is_all_day"] else 0,
            evt["status"],
            json.dumps(evt["attendees"]),
        ),
    )
    conn.commit()

    return _tool_result({
        "status": "ok",
        "event": evt,
    })


def _free_busy(conn: sqlite3.Connection, args: dict) -> str:
    items = args.get("items")
    if not items:
        items = [{"id": "primary"}]

    now = datetime.now(timezone.utc)
    time_min = args.get("time_min", now.isoformat())
    time_max = args.get("time_max", (now + timedelta(days=1)).isoformat())

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": items,
    }

    result = _calendar_request("/freeBusy", method="POST", body=body)
    calendars = result.get("calendars", [])

    formatted = []
    for cal in calendars:
        formatted.append({
            "id": cal.get("id", ""),
            "busy_slots": cal.get("busy", []),
            "errors": cal.get("errors", []),
        })

    return _tool_result({
        "status": "ok",
        "calendars": formatted,
        "time_min": time_min,
        "time_max": time_max,
    })


def _search_events(conn: sqlite3.Connection, args: dict) -> str:
    calendar_id = args.get("calendar_id", "primary")
    query = args.get("query")
    if not query:
        return _tool_error("query is required for search_events")

    max_results = min(int(args.get("max_results", 20)), 250)

    now = datetime.now(timezone.utc)
    time_min = args.get("time_min", (now - timedelta(days=30)).isoformat())
    time_max = args.get("time_max", (now + timedelta(days=365)).isoformat())

    params = urllib.parse.urlencode({
        "q": query,
        "maxResults": max_results,
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "timeMax": time_max,
    })

    result = _calendar_request(f"/calendars/{urllib.parse.quote(calendar_id)}/events?{params}")
    events = result.get("items", [])

    formatted = []
    for event in events:
        if event.get("status") == "cancelled":
            continue
        formatted.append(_format_event(event))

    return _tool_result({
        "status": "ok",
        "calendar_id": calendar_id,
        "query": query,
        "events": formatted,
        "count": len(formatted),
    })


def _share_fact(args: dict) -> str:
    fact = args.get("fact")
    if not fact:
        return _tool_error("fact is required for share_fact")

    domain = str(args.get("domain") or "scheduling").strip()

    try:
        from hermes_cli.plugins import call_tool
        result = call_tool(
            tool_name="share_knowledge",
            toolset="share_knowledge",
            args={
                "action": "write",
                "scope": "personal",
                "domain": domain,
                "fact": fact,
                "confidence": 0.9,
            },
        )
        return _tool_result({
            "status": "shared",
            "fact": fact,
            "scope": "personal",
            "domain": domain,
            "share_result": result,
        })
    except ImportError:
        return _tool_result({
            "status": "shared_local",
            "fact": fact,
            "note": "share_knowledge not available",
        })
