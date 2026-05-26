#!/usr/bin/env python3
"""WhatsApp safety scanner cron job.

Periodically scans recent WhatsApp messages through the safety scanner,
alerts on high-risk messages, and logs safety statistics.

Runs every 15 minutes via launchd.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/Users/roelvideler/openspec/Olympus")

from plugins.hermes.skills.whatsapp_safety import scan_message as safety_scan

BRIDGE_DB = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
OLYMPUS_DB = Path.home() / ".hermes" / "olympus.db"
SAFETY_LOG = Path.home() / ".hermes" / "whatsapp" / "safety-log.json"

RISK_THRESHOLD = 0.6  # Alert on messages below this score
SCAN_WINDOW_MINUTES = 30  # Only scan messages from last N minutes


def get_recent_messages() -> list[dict]:
    """Get messages from the last SCAN_WINDOW_MINUTES minutes."""
    if not BRIDGE_DB.exists():
        print(f"Bridge DB not found at {BRIDGE_DB}")
        return []

    conn = sqlite3.connect(str(BRIDGE_DB))
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SCAN_WINDOW_MINUTES)).isoformat()

    try:
        rows = conn.execute(
            """
            SELECT id, chat_jid, sender, content, timestamp, is_from_me
            FROM messages
            WHERE timestamp > ? AND is_from_me = 0
            ORDER BY timestamp DESC
            """,
            [cutoff],
        ).fetchall()

        return [
            {
                "id": row["id"],
                "chat_jid": row["chat_jid"],
                "sender": row["sender"],
                "content": row["content"] or "",
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def scan_messages(messages: list[dict]) -> list[dict]:
    """Scan messages through safety scanner."""
    results = []
    for msg in messages:
        content = msg["content"]
        if not content:
            continue

        result = safety_scan(content, msg["sender"], is_known_sender=True)
        results.append({
            "message_id": msg["id"],
            "chat_jid": msg["chat_jid"],
            "sender": msg["sender"],
            "timestamp": msg["timestamp"],
            "content_preview": content[:100],
            "safety_score": result["safety_score"],
            "risk_category": result["risk_category"],
            "threats": result["threats"],
            "is_blocked": result["is_blocked"],
        })

    return results


def log_results(results: list[dict]) -> None:
    """Append scan results to safety log."""
    SAFETY_LOG.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if SAFETY_LOG.exists():
        try:
            with open(SAFETY_LOG) as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            existing = []

    # Keep last 1000 entries
    existing.extend(results)
    existing = existing[-1000:]

    with open(SAFETY_LOG, "w") as f:
        json.dump(existing, f, indent=2)


def print_alerts(results: list[dict]) -> None:
    """Print alerts for high-risk messages."""
    alerts = [r for r in results if r["safety_score"] < RISK_THRESHOLD]

    if not alerts:
        print("No safety alerts.")
        return

    print(f"\n⚠️  {len(alerts)} high-risk message(s) detected:\n")
    for alert in alerts:
        print(f"  From: {alert['sender']}")
        print(f"  Time: {alert['timestamp']}")
        print(f"  Score: {alert['safety_score']} ({alert['risk_category']})")
        print(f"  Threats: {', '.join(alert['threats'])}")
        print(f"  Preview: {alert['content_preview']}")
        print()


def print_summary(results: list[dict]) -> None:
    """Print scan summary."""
    if not results:
        print(f"No new messages in last {SCAN_WINDOW_MINUTES} minutes.")
        return

    safe = sum(1 for r in results if r["risk_category"] == "safe")
    low = sum(1 for r in results if r["risk_category"] == "low_risk")
    medium = sum(1 for r in results if r["risk_category"] == "medium_risk")
    high = sum(1 for r in results if r["risk_category"] == "high_risk")
    critical = sum(1 for r in results if r["risk_category"] == "critical")

    print(f"\n=== WhatsApp Safety Scan Summary ===")
    print(f"Scanned: {len(results)} messages")
    print(f"Safe: {safe}, Low: {low}, Medium: {medium}, High: {high}, Critical: {critical}")
    print(f"Blocked: {sum(1 for r in results if r['is_blocked'])}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")


def main() -> None:
    """Run the safety scanner."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting WhatsApp safety scan...")

    messages = get_recent_messages()
    if not messages:
        print(f"No new messages in last {SCAN_WINDOW_MINUTES} minutes.")
        return

    results = scan_messages(messages)
    log_results(results)
    print_summary(results)
    print_alerts(results)


if __name__ == "__main__":
    main()
