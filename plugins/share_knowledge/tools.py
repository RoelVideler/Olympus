"""Share knowledge tool — cross-agent knowledge sharing for Olympus.

Security model:
- Scope enforcement: Each profile has allowed read/write scopes loaded from scopes.json.
- source_profile: Derived from Hermes' get_active_profile_name(), not user-supplied.
- Delete: Requires id, verifies scope ownership before deletion.
- Database path: Validated to be within ~/.hermes/ directory.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Literal


def tool_error(message, **extra) -> str:
    result = {"error": str(message)}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def tool_result(data=None, **kwargs) -> str:
    if data is not None:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(kwargs, ensure_ascii=False)


# Database path — validated to be within ~/.hermes/
_DEFAULT_DB_PATH = Path.home() / ".hermes" / "olympus.db"

def _resolve_db_path() -> Path:
    """Resolve and validate the database path."""
    env_path = os.environ.get("OLYMPUS_DB_PATH")
    if env_path:
        resolved = Path(env_path).resolve()
        hermes_home = Path.home() / ".hermes"
        # Validate: must be under ~/.hermes/
        try:
            resolved.relative_to(hermes_home.resolve())
        except ValueError:
            # Path is outside ~/.hermes/, use default
            return _DEFAULT_DB_PATH
        return resolved
    return _DEFAULT_DB_PATH

DEFAULT_DB_PATH = _resolve_db_path()

# Schema can live in multiple locations — check in order
_SCHEMA_CANDIDATES = [
    Path(__file__).resolve().parent / "schema" / "001_initial.sql",
    Path.home() / ".hermes" / "plugins" / "share_knowledge" / "schema" / "001_initial.sql",
]


def _find_schema() -> Path | None:
    for candidate in _SCHEMA_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_scope_config(path: str) -> dict[str, dict[str, list[str]]]:
    """Load scope configuration from JSON file."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


SHARE_KNOWLEDGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "share_knowledge",
        "description": "Write, query, or delete cross-agent knowledge facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["write", "query", "delete"],
                    "description": "Action to perform: write a fact, query facts, or delete a fact.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["personal", "business", "global"],
                    "description": "Knowledge scope: personal, business, or global.",
                },
                "domain": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Domain category for the fact (e.g., 'health', 'preferences', 'projects'). Max 100 chars.",
                },
                "fact": {
                    "type": "string",
                    "maxLength": 10000,
                    "description": "The fact to write or delete. Required for write. For delete, provide either fact or id.",
                },
                "id": {
                    "type": "string",
                    "description": "The fact id to delete. Required for delete action.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 1.0,
                    "description": "Confidence level for the fact (0.0 to 1.0). Default: 1.0.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Maximum number of facts to return for query action. Default: 10.",
                },
            },
            "required": ["action", "scope", "domain"],
        },
    },
}


def _get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a connection to the Olympus knowledge database."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure the database schema exists."""
    schema_file = _find_schema()
    if schema_file:
        with open(schema_file) as f:
            conn.executescript(f.read())


def _get_calling_profile() -> str:
    """Get the calling profile name from Hermes context."""
    try:
        from hermes_cli.profiles import get_active_profile_name
        return get_active_profile_name()
    except ImportError:
        return "unknown"


def _check_scope(scope: str, profile: str, action: str, scope_config: dict) -> str | None:
    """Check if a profile is authorized for the given scope and action.

    Returns None if authorized, or an error message string if not.
    """
    profile_scopes = scope_config.get(profile, {})
    if not profile_scopes:
        # No config for this profile — deny all access
        return f"Profile '{profile}' has no scope configuration"

    allowed = profile_scopes.get(action, [])  # action is "read" or "write"
    if scope not in allowed:
        return f"Profile '{profile}' not authorized for {action} on scope '{scope}'. Allowed: {allowed}"

    return None


def _handle_share_knowledge(args: dict, scope_config: dict | None = None, **kw) -> str:
    """Handle share_knowledge tool calls with scope enforcement."""
    action = str(args.get("action") or "").strip().lower()
    scope = str(args.get("scope") or "").strip().lower()
    domain = str(args.get("domain") or "").strip()

    if action not in ("write", "query", "delete"):
        return tool_error(f"Unknown action: {action}. Must be one of: write, query, delete")

    if scope not in ("personal", "business", "global"):
        return tool_error(f"Unknown scope: {scope}. Must be one of: personal, business, global")

    if not domain:
        return tool_error("domain is required")

    # Validate domain length
    if len(domain) > 100:
        return tool_error(f"domain too long: {len(domain)} chars (max 100)")

    # Get calling profile identity from Hermes
    profile = _get_calling_profile()

    # Scope enforcement
    if scope_config:
        read_write = "write" if action == "write" else "read"
        error = _check_scope(scope, profile, read_write, scope_config)
        if error:
            return tool_error(error)

    try:
        conn = _get_db()
        _ensure_schema(conn)
    except Exception as e:
        return tool_error(f"Database connection failed: {e}")

    try:
        if action == "write":
            return _write(conn, scope, domain, args, profile)
        elif action == "query":
            return _query(conn, scope, domain, args)
        elif action == "delete":
            return _delete(conn, scope, domain, args, profile, scope_config)
    except Exception as e:
        return tool_error(f"share_knowledge failed: {type(e).__name__}: {e}")
    finally:
        conn.close()


def _write(conn: sqlite3.Connection, scope: str, domain: str, args: dict, profile: str) -> str:
    fact = args.get("fact")
    if not fact:
        return tool_error("fact is required for write action")

    # Validate fact length
    if len(fact) > 10000:
        return tool_error(f"fact too long: {len(fact)} chars (max 10000)")

    confidence = float(args.get("confidence", 1.0))
    if confidence < 0.0 or confidence > 1.0:
        return tool_error("confidence must be between 0.0 and 1.0")

    # source_profile comes from Hermes context, NOT from user-supplied args
    source_profile = profile
    fact_id = str(uuid.uuid4())

    conn.execute(
        """
        INSERT INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (fact_id, scope, domain, fact, confidence, source_profile),
    )
    conn.commit()
    return tool_result({"status": "written", "id": fact_id})


def _query(conn: sqlite3.Connection, scope: str, domain: str, args: dict) -> str:
    limit = int(args.get("limit", 10))
    limit = max(1, min(100, limit))

    rows = conn.execute(
        """
        SELECT id, domain, fact, confidence, source_profile, created_at
        FROM olympus_knowledge
        WHERE scope = ? AND domain = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT ?
        """,
        (scope, domain, limit),
    ).fetchall()

    return tool_result({
        "status": "ok",
        "facts": [
            {
                "id": row["id"],
                "domain": row["domain"],
                "fact": row["fact"],
                "confidence": row["confidence"],
                "source_profile": row["source_profile"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "count": len(rows),
    })


def _delete(conn: sqlite3.Connection, scope: str, domain: str, args: dict, profile: str, scope_config: dict | None) -> str:
    fact_id = args.get("id")
    fact = args.get("fact")

    if fact:
        return tool_error("delete by fact text is deprecated — use id instead")

    if not fact_id:
        return tool_error("id is required for delete action")

    # Fetch the row to verify scope ownership
    row = conn.execute(
        "SELECT id, scope FROM olympus_knowledge WHERE id = ?",
        (fact_id,),
    ).fetchone()

    if row is None:
        return tool_result({"status": "deleted", "rows_affected": 0})

    # Verify the calling profile is authorized for this scope
    if scope_config:
        error = _check_scope(row["scope"], profile, "write", scope_config)
        if error:
            return tool_error(error)

    cursor = conn.execute(
        "DELETE FROM olympus_knowledge WHERE id = ?",
        (fact_id,),
    )
    conn.commit()
    return tool_result({"status": "deleted", "rows_affected": cursor.rowcount})
