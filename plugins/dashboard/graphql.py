"""GraphQL endpoint for the Dashboard plugin.

Provides complex queries spanning multiple data types:
- health, calendar, wiki, contacts, preferences types
- Single response for combined queries
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Try to import graphene; fall back to manual JSON query parsing if unavailable
try:
    import graphene
    GRAPHENE_AVAILABLE = True
except ImportError:
    GRAPHENE_AVAILABLE = True  # We'll use a lightweight fallback
    graphene = None  # type: ignore

from .api import get_db, _rows_to_dict


class HealthType:
    """Health data type."""

    @staticmethod
    def resolve(conn) -> Dict[str, Any]:
        result = {"status": "ok", "profiles": [], "knowledge_stats": []}
        try:
            cursor = conn.execute(
                "SELECT name, status, run_mode FROM agent_profiles ORDER BY name"
            )
            result["profiles"] = _rows_to_dict(cursor.fetchall())

            cursor = conn.execute(
                "SELECT scope, COUNT(*) as count FROM olympus_knowledge GROUP BY scope"
            )
            result["knowledge_stats"] = _rows_to_dict(cursor.fetchall())
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        return result


class WikiEntryType:
    """Wiki entry type."""

    @staticmethod
    def resolve(conn, domain: Optional[str] = None, scope: Optional[str] = None) -> list:
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
        return _rows_to_dict(cursor.fetchall())


class CalendarEventType:
    """Calendar event type."""

    @staticmethod
    def resolve(conn) -> list:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'"
        )
        if not cursor.fetchone():
            return []
        cursor = conn.execute("SELECT * FROM calendar_events ORDER BY start_time ASC")
        return _rows_to_dict(cursor.fetchall())


class ContactType:
    """Contact type."""

    @staticmethod
    def resolve(conn) -> list:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
        )
        if not cursor.fetchone():
            return []
        cursor = conn.execute("SELECT * FROM contacts ORDER BY name ASC")
        return _rows_to_dict(cursor.fetchall())


class PreferencesType:
    """Preferences type."""

    @staticmethod
    def resolve(conn) -> Dict[str, Any]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='preferences'"
        )
        if not cursor.fetchone():
            return {}
        cursor = conn.execute("SELECT key, value FROM preferences")
        return {row["key"]: row["value"] for row in cursor.fetchall()}


def _execute_query(query_str: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute a GraphQL-like query against the SQLite database.

    Lightweight fallback that parses simple JSON-style queries:
    { health { ... }, wiki { ... }, calendar { ... }, contacts { ... }, preferences { ... } }
    """
    conn = get_db()
    if conn is None:
        return {"data": {}, "error": "Database not found"}

    result: Dict[str, Any] = {}
    try:
        # Parse requested fields from the query string
        requested_fields = []
        for field in ["health", "wiki", "calendar", "contacts", "preferences"]:
            if field in query_str:
                requested_fields.append(field)

        if "health" in requested_fields:
            result["health"] = HealthType.resolve(conn)

        if "wiki" in requested_fields:
            domain = variables.get("domain") if variables else None
            scope = variables.get("scope") if variables else None
            result["wiki"] = WikiEntryType.resolve(conn, domain=domain, scope=scope)

        if "calendar" in requested_fields:
            result["calendar"] = CalendarEventType.resolve(conn)

        if "contacts" in requested_fields:
            result["contacts"] = ContactType.resolve(conn)

        if "preferences" in requested_fields:
            result["preferences"] = PreferencesType.resolve(conn)

        return {"data": result}
    except Exception as e:
        logger.error("GraphQL query failed: %s", e)
        return {"data": result, "errors": [{"message": str(e)}]}
    finally:
        conn.close()


async def handle_graphql(request: web.Request) -> web.Response:
    """POST /api/graphql — handle GraphQL queries."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"errors": [{"message": "Invalid JSON body"}]},
            status=400,
        )

    query = body.get("query", "")
    variables = body.get("variables")

    if not query:
        return web.json_response(
            {"errors": [{"message": "query is required"}]},
            status=400,
        )

    result = _execute_query(query, variables)
    status_code = 200 if "errors" not in result else 200  # GraphQL always returns 200
    return web.json_response(result, status=status_code)


def register_graphql_route(app: web.Application) -> None:
    """Register the GraphQL route."""
    app.router.add_post("/api/graphql", handle_graphql)
    app.router.add_get("/api/graphql", handle_graphql)  # Allow GET for simple queries
