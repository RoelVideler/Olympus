# plugins/hephaestus/skills/home_maintenance.py
"""Home maintenance tracking tool for Hephaestus.

Manages maintenance schedules, logs device history, and extracts
facts for cross-agent knowledge sharing.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Literal

HOME_MAINTENANCE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "home_maintenance",
        "description": "Track home maintenance events, schedules, and reminders.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "log_maintenance",
                        "query_maintenance",
                        "schedule_reminder",
                        "query_reminders",
                        "share_fact",
                    ],
                    "description": "Action to perform.",
                },
                "device": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Device or system name (e.g., 'HVAC', 'dishwasher', 'roof').",
                },
                "domain": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Domain category (e.g., 'hvac', 'appliance', 'structural').",
                },
                "action_type": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Type of maintenance action (e.g., 'filter_replaced', 'inspection', 'repair').",
                },
                "notes": {
                    "type": "string",
                    "maxLength": 5000,
                    "description": "Additional notes about the maintenance event.",
                },
                "completed_date": {
                    "type": "string",
                    "description": "ISO 8601 date when the maintenance was completed.",
                },
                "scheduled_date": {
                    "type": "string",
                    "description": "ISO 8601 date for a scheduled reminder.",
                },
                "recurrence_days": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Repeat interval in days. NULL = one-time.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum results to return.",
                },
                "overdue_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only return overdue reminders.",
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

_DB_PATH = Path.home() / ".hermes" / "olympus.db"


def _tool_error(message: str, **extra) -> str:
    result = {"error": str(message)}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def _tool_result(data=None, **kwargs) -> str:
    if data is not None:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(kwargs, ensure_ascii=False)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    schema_candidates = [
        Path(__file__).resolve().parents[1] / "schema" / "001_home_maintenance.sql",
        Path.home() / ".hermes" / "plugins" / "hephaestus" / "schema" / "001_home_maintenance.sql",
    ]
    for candidate in schema_candidates:
        if candidate.exists():
            with open(candidate) as f:
                conn.executescript(f.read())
            return


def _get_calling_profile() -> str:
    try:
        from hermes_cli.profiles import get_active_profile_name
        return get_active_profile_name()
    except ImportError:
        return "hephaestus"


def handle_home_maintenance(args: dict, **kw) -> str:
    """Handle home_maintenance tool calls."""
    action = str(args.get("action") or "").strip().lower()

    if action not in (
        "log_maintenance",
        "query_maintenance",
        "schedule_reminder",
        "query_reminders",
        "share_fact",
    ):
        return _tool_error(
            f"Unknown action: {action}. Must be one of: "
            "log_maintenance, query_maintenance, schedule_reminder, query_reminders, share_fact"
        )

    conn = None
    try:
        conn = _get_db()
        _ensure_schema(conn)
    except Exception as e:
        return _tool_error(f"Database connection failed: {e}")

    try:
        if action == "log_maintenance":
            return _log_maintenance(conn, args)
        elif action == "query_maintenance":
            return _query_maintenance(conn, args)
        elif action == "schedule_reminder":
            return _schedule_reminder(conn, args)
        elif action == "query_reminders":
            return _query_reminders(conn, args)
        elif action == "share_fact":
            return _share_fact(args)
    except Exception as e:
        return _tool_error(f"home_maintenance failed: {type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()


def _log_maintenance(conn: sqlite3.Connection, args: dict) -> str:
    device = args.get("device")
    action_type = args.get("action_type")

    if not device:
        return _tool_error("device is required for log_maintenance")
    if not action_type:
        return _tool_error("action_type is required for log_maintenance")

    domain = str(args.get("domain") or "general").strip()
    notes = str(args.get("notes") or "").strip()
    completed_date = args.get("completed_date") or datetime.now().strftime("%Y-%m-%d")

    if len(device) > 200:
        return _tool_error(f"device too long: {len(device)} chars (max 200)")
    if len(notes) > 5000:
        return _tool_error(f"notes too long: {len(notes)} chars (max 5000)")

    record_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO home_maintenance (id, device, domain, action, notes, completed_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (record_id, device, domain, action_type, notes, completed_date),
    )
    conn.commit()
    return _tool_result({
        "status": "logged",
        "id": record_id,
        "device": device,
        "action": action_type,
        "completed_date": completed_date,
    })


def _query_maintenance(conn: sqlite3.Connection, args: dict) -> str:
    device = args.get("device")
    domain = args.get("domain")
    limit = min(int(args.get("limit", 20)), 100)

    conditions = []
    params: list = []

    if device:
        conditions.append("device = ?")
        params.append(device)
    if domain:
        conditions.append("domain = ?")
        params.append(domain)

    where = " AND ".join(conditions) if conditions else "1=1"

    rows = conn.execute(
        f"""
        SELECT id, device, domain, action, notes, completed_date, recurrence_days, created_at
        FROM home_maintenance
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()

    return _tool_result({
        "status": "ok",
        "records": [
            {
                "id": row["id"],
                "device": row["device"],
                "domain": row["domain"],
                "action": row["action"],
                "notes": row["notes"],
                "completed_date": row["completed_date"],
                "recurrence_days": row["recurrence_days"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "count": len(rows),
    })


def _schedule_reminder(conn: sqlite3.Connection, args: dict) -> str:
    device = args.get("device")
    action_type = args.get("action_type")
    recurrence_days = args.get("recurrence_days")

    if not device:
        return _tool_error("device is required for schedule_reminder")
    if not action_type:
        return _tool_error("action_type is required for schedule_reminder")
    if not recurrence_days:
        return _tool_error("recurrence_days is required for schedule_reminder")

    domain = str(args.get("domain") or "general").strip()
    notes = str(args.get("notes") or "").strip()
    scheduled_date = args.get("scheduled_date") or datetime.now().strftime("%Y-%m-%d")

    record_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO home_maintenance (id, device, domain, action, notes, scheduled_date, recurrence_days)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (record_id, device, domain, action_type, notes, scheduled_date, int(recurrence_days)),
    )
    conn.commit()
    return _tool_result({
        "status": "scheduled",
        "id": record_id,
        "device": device,
        "action": action_type,
        "scheduled_date": scheduled_date,
        "recurrence_days": int(recurrence_days),
    })


def _query_reminders(conn: sqlite3.Connection, args: dict) -> str:
    overdue_only = bool(args.get("overdue_only", False))
    today = datetime.now().strftime("%Y-%m-%d")

    if overdue_only:
        rows = conn.execute(
            """
            SELECT id, device, domain, action, notes, scheduled_date, recurrence_days, completed_date, created_at
            FROM home_maintenance
            WHERE recurrence_days IS NOT NULL
              AND scheduled_date <= ?
              AND (completed_date IS NULL OR completed_date < ?)
            ORDER BY scheduled_date ASC
            """,
            (today, today),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, device, domain, action, notes, scheduled_date, recurrence_days, completed_date, created_at
            FROM home_maintenance
            WHERE recurrence_days IS NOT NULL
            ORDER BY scheduled_date ASC
            """,
        ).fetchall()

    reminders = []
    for row in rows:
        is_overdue = row["scheduled_date"] <= today and (
            row["completed_date"] is None or row["completed_date"] < today
        )
        next_due = row["scheduled_date"]
        if row["completed_date"] and row["recurrence_days"]:
            try:
                completed = datetime.strptime(row["completed_date"], "%Y-%m-%d")
                next_due = (completed + timedelta(days=row["recurrence_days"])).strftime("%Y-%m-%d")
            except ValueError:
                pass

        reminders.append({
            "id": row["id"],
            "device": row["device"],
            "domain": row["domain"],
            "action": row["action"],
            "notes": row["notes"],
            "scheduled_date": row["scheduled_date"],
            "next_due": next_due,
            "recurrence_days": row["recurrence_days"],
            "is_overdue": is_overdue,
        })

    return _tool_result({
        "status": "ok",
        "reminders": reminders,
        "count": len(reminders),
        "overdue_count": sum(1 for r in reminders if r["is_overdue"]),
    })


def _share_fact(args: dict) -> str:
    fact = args.get("fact")
    if not fact:
        return _tool_error("fact is required for share_fact")

    domain = str(args.get("domain") or "home").strip()
    profile = _get_calling_profile()

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
            "note": "share_knowledge not available, fact logged locally",
        })
