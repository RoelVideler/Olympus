# plugins/iaso/skills/withings_sync.py
"""Withings health sync tool for Iaso.

Fetches, stores, and queries health data from Withings devices.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import httpx

WITHINGS_SYNC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "withings_sync",
        "description": "Sync and query health data from Withings devices.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "sync_data",
                        "query_vitals",
                        "query_sleep",
                        "query_activity",
                        "sync_status",
                        "share_fact",
                    ],
                    "description": "Action to perform.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD). Defaults to 7 days ago for sync/query.",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD). Defaults to today.",
                },
                "vitals_type": {
                    "type": "string",
                    "description": "Vital type to filter by (weight, bp_systolic, bp_diastolic, pulse, temperature, spo2).",
                },
                "types": {
                    "type": "string",
                    "description": "Comma-separated measurement types to sync (default: all).",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum results to return.",
                },
                "fact": {
                    "type": "string",
                    "maxLength": 10000,
                    "description": "Fact to share via share_knowledge (for share_fact action).",
                },
                "domain": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Domain for share_fact (default: health).",
                },
            },
            "required": ["action"],
        },
    },
}

WITHINGS_BASE = "https://wbsapi.withings.net"
_DB_PATH = Path.home() / ".hermes" / "olympus.db"

MEASUREMENT_TYPE_MAP = {
    1: "weight",
    4: "height",
    5: "fat_free_mass",
    6: "fat_ratio",
    8: "fat_mass_weight",
    9: "bp_diastolic",
    10: "bp_systolic",
    11: "pulse",
    12: "temperature",
    54: "spo2",
    76: "muscle_mass",
    77: "hydration",
    88: "bone_mass",
    91: "pulse_wave_velocity",
    123: "vo2_max",
}


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
        Path(__file__).resolve().parents[1] / "schema" / "001_withings_sync.sql",
        Path.home() / ".hermes" / "plugins" / "iaso" / "schema" / "001_withings_sync.sql",
    ]
    for candidate in schema_candidates:
        if candidate.exists():
            with open(candidate) as f:
                conn.executescript(f.read())
            return


def _get_access_token() -> str:
    try:
        from .withings_auth import get_access_token
        token = get_access_token()
        if not token:
            raise RuntimeError("No valid Withings access token. Please re-authorize.")
        return token
    except ImportError:
        from withings_auth import get_access_token
        token = get_access_token()
        if not token:
            raise RuntimeError("No valid Withings access token. Please re-authorize.")
        return token


def _get_userid() -> str:
    try:
        from .withings_auth import get_userid
        userid = get_userid()
        if not userid:
            raise RuntimeError("No Withings user ID found.")
        return userid
    except ImportError:
        from withings_auth import get_userid
        userid = get_userid()
        if not userid:
            raise RuntimeError("No Withings user ID found.")
        return userid


def _fetch_measurements(access_token: str, startdate: int, enddate: int) -> list[dict]:
    response = httpx.post(f"{WITHINGS_BASE}/measure", headers={
        "Authorization": f"Bearer {access_token}",
    }, data={
        "action": "getmeas",
        "startdate": startdate,
        "enddate": enddate,
        "format": "2",
    }, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Withings API error: {response.status_code} {response.text}")

    data = response.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Withings API error status: {data.get('status')}")

    body = data.get("body", {})
    groups = body.get("measuregrps", [])
    measurements = []
    for group in groups:
        date_ts = group.get("date", 0)
        for m in group.get("meas", []):
            if m.get("value") is not None:
                value = m["value"] * (10 ** m.get("unit", 0))
                measurements.append({
                    "type": m.get("type"),
                    "value": value,
                    "unit": m.get("unit", ""),
                    "date": datetime.fromtimestamp(date_ts).strftime("%Y-%m-%dT%H:%M:%S"),
                })
    return measurements


def _fetch_sleep(access_token: str, date_from: str, date_to: str) -> list[dict]:
    response = httpx.post(f"{WITHINGS_BASE}/v2/sleep", headers={
        "Authorization": f"Bearer {access_token}",
    }, data={
        "action": "getsummary",
        "startdateymd": date_from,
        "enddateymd": date_to,
    }, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Withings API error: {response.status_code}")

    data = response.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Withings API error status: {data.get('status')}")

    body = data.get("body", {})
    series = body.get("series", [])
    sleep_data = []
    for entry in series:
        for model in entry.get("model", []):
            if model.get("type") == 0:
                data_points = {dp["type"]: dp["value"] for dp in model.get("data", [])}
                sleep_data.append({
                    "date": entry.get("startdate", "")[:10],
                    "sleep_score": data_points.get(2),
                    "total_sleep_seconds": data_points.get(0),
                    "rem_seconds": data_points.get(3),
                    "deep_sleep_seconds": data_points.get(4),
                    "light_sleep_seconds": data_points.get(5),
                    "awake_seconds": data_points.get(1),
                    "hr_average": data_points.get(8),
                    "hr_min": data_points.get(9),
                    "hr_max": data_points.get(10),
                    "spo2_average": data_points.get(11),
                    "snoring_seconds": data_points.get(12),
                })
    return sleep_data


def _fetch_activity(access_token: str, date_from: str, date_to: str) -> list[dict]:
    response = httpx.post(f"{WITHINGS_BASE}/v2/measure", headers={
        "Authorization": f"Bearer {access_token}",
    }, data={
        "action": "getactivity",
        "startdateymd": date_from,
        "enddateymd": date_to,
        "data_fields": "steps,distance,elevation,calories,totalcalories,hr_average,hr_min,hr_max,active",
    }, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Withings API error: {response.status_code}")

    data = response.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Withings API error status: {data.get('status')}")

    body = data.get("body", {})
    activities = body.get("activities", [])
    return [
        {
            "date": a.get("date", ""),
            "steps": a.get("steps"),
            "distance": a.get("distance"),
            "elevation": a.get("elevation"),
            "calories": a.get("calories"),
            "total_calories": a.get("totalcalories"),
            "hr_average": a.get("hr_average"),
            "hr_min": a.get("hr_min"),
            "hr_max": a.get("hr_max"),
            "active_seconds": a.get("active"),
        }
        for a in activities
    ]


def handle_withings_sync(args: dict, **kw) -> str:
    """Handle withings_sync tool calls."""
    action = str(args.get("action") or "").strip().lower()

    valid_actions = (
        "sync_data", "query_vitals", "query_sleep",
        "query_activity", "sync_status", "share_fact",
    )
    if action not in valid_actions:
        return _tool_error(
            f"Unknown action: {action}. Must be one of: {', '.join(valid_actions)}"
        )

    try:
        if action == "sync_data":
            return _sync_data(args)
        elif action == "query_vitals":
            return _query_vitals(args)
        elif action == "query_sleep":
            return _query_sleep(args)
        elif action == "query_activity":
            return _query_activity(args)
        elif action == "sync_status":
            return _sync_status()
        elif action == "share_fact":
            return _share_fact(args)
    except Exception as e:
        return _tool_error(f"withings_sync failed: {type(e).__name__}: {e}")


def _sync_data(args: dict) -> str:
    try:
        access_token = _get_access_token()
        userid = _get_userid()
    except RuntimeError as e:
        return _tool_error(str(e))

    date_to = args.get("date_to") or datetime.now().strftime("%Y-%m-%d")
    date_from = args.get("date_from") or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(date_to, "%Y-%m-%d").timestamp()) + 86399

    results = {"measurements": 0, "sleep": 0, "activity": 0}

    try:
        conn = _get_db()
        _ensure_schema(conn)

        measurements = _fetch_measurements(access_token, start_ts, end_ts)
        for m in measurements:
            vitals_type = MEASUREMENT_TYPE_MAP.get(m["type"])
            if not vitals_type:
                continue
            record_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO withings_vitals
                       (id, userid, vitals_type, value, unit, measured_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (record_id, userid, vitals_type, m["value"], str(m["unit"]), m["date"]),
                )
                results["measurements"] += 1
            except sqlite3.IntegrityError:
                pass

        sleep_data = _fetch_sleep(access_token, date_from, date_to)
        for s in sleep_data:
            record_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO withings_sleep
                       (id, userid, date, sleep_score, total_sleep_seconds,
                        rem_seconds, deep_sleep_seconds, light_sleep_seconds,
                        awake_seconds, hr_average, hr_min, hr_max,
                        spo2_average, snoring_seconds)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (record_id, userid, s["date"], s.get("sleep_score"),
                     s.get("total_sleep_seconds"), s.get("rem_seconds"),
                     s.get("deep_sleep_seconds"), s.get("light_sleep_seconds"),
                     s.get("awake_seconds"), s.get("hr_average"),
                     s.get("hr_min"), s.get("hr_max"),
                     s.get("spo2_average"), s.get("snoring_seconds")),
                )
                results["sleep"] += 1
            except sqlite3.IntegrityError:
                pass

        activities = _fetch_activity(access_token, date_from, date_to)
        for a in activities:
            record_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO withings_activity
                       (id, userid, date, steps, distance, elevation,
                        calories, total_calories, hr_average, hr_min,
                        hr_max, active_seconds)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (record_id, userid, a["date"], a.get("steps"),
                     a.get("distance"), a.get("elevation"),
                     a.get("calories"), a.get("total_calories"),
                     a.get("hr_average"), a.get("hr_min"),
                     a.get("hr_max"), a.get("active_seconds")),
                )
                results["activity"] += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()
    except Exception as e:
        return _tool_error(f"Sync failed: {type(e).__name__}: {e}")

    return _tool_result({
        "status": "synced",
        "date_from": date_from,
        "date_to": date_to,
        **results,
        "synced_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })


def _query_vitals(args: dict) -> str:
    vitals_type = args.get("vitals_type")
    date_from = args.get("date_from")
    date_to = args.get("date_to") or datetime.now().strftime("%Y-%m-%d")
    limit = min(int(args.get("limit", 20)), 100)

    conditions = []
    params: list = []
    if vitals_type:
        conditions.append("vitals_type = ?")
        params.append(vitals_type)
    if date_from:
        conditions.append("measured_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("measured_at <= ?")
        params.append(date_to)

    where = " AND ".join(conditions) if conditions else "1=1"

    try:
        conn = _get_db()
        _ensure_schema(conn)
        rows = conn.execute(
            f"""SELECT id, vitals_type, value, unit, measured_at, synced_at
                FROM withings_vitals WHERE {where}
                ORDER BY measured_at DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        conn.close()
    except Exception as e:
        return _tool_error(f"Query failed: {e}")

    return _tool_result({
        "status": "ok",
        "records": [
            {
                "vitals_type": row["vitals_type"],
                "value": row["value"],
                "unit": row["unit"],
                "measured_at": row["measured_at"],
            }
            for row in rows
        ],
        "count": len(rows),
    })


def _query_sleep(args: dict) -> str:
    date_from = args.get("date_from")
    date_to = args.get("date_to") or datetime.now().strftime("%Y-%m-%d")
    limit = min(int(args.get("limit", 20)), 100)

    conditions = []
    params: list = []
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)

    where = " AND ".join(conditions) if conditions else "1=1"

    try:
        conn = _get_db()
        _ensure_schema(conn)
        rows = conn.execute(
            f"""SELECT id, date, sleep_score, total_sleep_seconds, rem_seconds,
                deep_sleep_seconds, light_sleep_seconds, awake_seconds,
                hr_average, hr_min, hr_max, spo2_average, snoring_seconds
                FROM withings_sleep WHERE {where}
                ORDER BY date DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        conn.close()
    except Exception as e:
        return _tool_error(f"Query failed: {e}")

    return _tool_result({
        "status": "ok",
        "records": [
            {
                "date": row["date"],
                "sleep_score": row["sleep_score"],
                "total_sleep_seconds": row["total_sleep_seconds"],
                "rem_seconds": row["rem_seconds"],
                "deep_sleep_seconds": row["deep_sleep_seconds"],
                "light_sleep_seconds": row["light_sleep_seconds"],
                "awake_seconds": row["awake_seconds"],
                "hr_average": row["hr_average"],
                "hr_min": row["hr_min"],
                "hr_max": row["hr_max"],
                "spo2_average": row["spo2_average"],
                "snoring_seconds": row["snoring_seconds"],
            }
            for row in rows
        ],
        "count": len(rows),
    })


def _query_activity(args: dict) -> str:
    date_from = args.get("date_from")
    date_to = args.get("date_to") or datetime.now().strftime("%Y-%m-%d")
    limit = min(int(args.get("limit", 20)), 100)

    conditions = []
    params: list = []
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)

    where = " AND ".join(conditions) if conditions else "1=1"

    try:
        conn = _get_db()
        _ensure_schema(conn)
        rows = conn.execute(
            f"""SELECT id, date, steps, distance, elevation, calories,
                total_calories, hr_average, hr_min, hr_max, active_seconds
                FROM withings_activity WHERE {where}
                ORDER BY date DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        conn.close()
    except Exception as e:
        return _tool_error(f"Query failed: {e}")

    return _tool_result({
        "status": "ok",
        "records": [
            {
                "date": row["date"],
                "steps": row["steps"],
                "distance": row["distance"],
                "elevation": row["elevation"],
                "calories": row["calories"],
                "total_calories": row["total_calories"],
                "hr_average": row["hr_average"],
                "hr_min": row["hr_min"],
                "hr_max": row["hr_max"],
                "active_seconds": row["active_seconds"],
            }
            for row in rows
        ],
        "count": len(rows),
    })


def _sync_status() -> str:
    try:
        from withings_auth import load_token
        token = load_token()
        token_valid = bool(token) and token.get("expires_at", 0) > __import__("time").time()
    except ImportError:
        token_valid = False

    try:
        conn = _get_db()
        _ensure_schema(conn)
        vitals_count = conn.execute("SELECT COUNT(*) FROM withings_vitals").fetchone()[0]
        sleep_count = conn.execute("SELECT COUNT(*) FROM withings_sleep").fetchone()[0]
        activity_count = conn.execute("SELECT COUNT(*) FROM withings_activity").fetchone()[0]
        last_sync = conn.execute(
            "SELECT MAX(synced_at) FROM (SELECT synced_at FROM withings_vitals UNION ALL SELECT synced_at FROM withings_sleep UNION ALL SELECT synced_at FROM withings_activity)"
        ).fetchone()[0]
        conn.close()
    except Exception:
        vitals_count = sleep_count = activity_count = 0
        last_sync = None

    return _tool_result({
        "status": "ok",
        "token_valid": token_valid,
        "vitals_count": vitals_count,
        "sleep_count": sleep_count,
        "activity_count": activity_count,
        "last_sync": last_sync,
    })


def _share_fact(args: dict) -> str:
    fact = args.get("fact")
    if not fact:
        return _tool_error("fact is required for share_fact")

    domain = str(args.get("domain") or "health").strip()

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
