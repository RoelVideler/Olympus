# plugins/hermes/skills/whatsapp_reader.py
"""WhatsApp reader tool for Hermes.

Connects to the WhatsApp MCP bridge to read messages, list chats,
and search contacts. All incoming messages pass through the safety
scanner before being returned — injection attempts are neutralized.

Bridge must be running on localhost with a valid auth token.
Token stored at ~/.hermes/whatsapp/bridge-token (symlinked from bridge store).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .whatsapp_safety import scan_message as safety_scan

BRIDGE_TOKEN_PATH = Path.home() / ".hermes" / "whatsapp" / "bridge-token"
DB_PATH = Path.home() / ".hermes" / "olympus.db"

WHATSAPP_READER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "whatsapp_reader",
        "description": "Read WhatsApp messages, list chats, and search contacts. All messages are safety-scanned before return.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list_chats",
                        "get_messages",
                        "search_contacts",
                        "get_contact_chats",
                        "get_last_interaction",
                        "get_message_context",
                        "share_fact",
                    ],
                    "description": "Action to perform.",
                },
                "chat_jid": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Chat JID for get_messages or get_message_context.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum results to return.",
                },
                "phone": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Phone number for contact operations.",
                },
                "query": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Search query for contacts.",
                },
                "message_id": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Message ID for get_message_context.",
                },
                "before": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 50,
                    "default": 5,
                    "description": "Messages before target for context.",
                },
                "after": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 50,
                    "default": 5,
                    "description": "Messages after target for context.",
                },
                "min_safety_score": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.0,
                    "description": "Only return messages with safety score >= this value.",
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
        CREATE TABLE IF NOT EXISTS whatsapp_message_cache (
            id TEXT PRIMARY KEY,
            message_id TEXT,
            chat_jid TEXT,
            sender TEXT,
            sender_display TEXT,
            original_text TEXT,
            sanitized_text TEXT,
            safety_score REAL,
            risk_category TEXT,
            threats TEXT,
            timestamp TEXT,
            is_from_me INTEGER DEFAULT 0,
            cached_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS whatsapp_chat_cache (
            jid TEXT PRIMARY KEY,
            name TEXT,
            is_group INTEGER DEFAULT 0,
            last_message_time TEXT,
            last_message TEXT,
            last_sender TEXT,
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


def _get_bridge_token() -> str:
    # Try Keychain first via credential module
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from olympus.credentials import get_credential
    token = get_credential("whatsapp", "bridge_token")
    if token:
        return token

    # Fallback to file
    if not BRIDGE_TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"WhatsApp bridge token not found at {BRIDGE_TOKEN_PATH}. "
            "Run the bridge first to generate it, then symlink to ~/.hermes/whatsapp/bridge-token"
        )
    return BRIDGE_TOKEN_PATH.read_text().strip()


def _bridge_request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    token = _get_bridge_token()
    # Default bridge port is 8080, but we use a high ephemeral port
    import os
    port = os.environ.get("WHATSAPP_BRIDGE_PORT", "36569")
    url = f"http://127.0.0.1:{port}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if body:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _safe_message(text: str, sender: str, is_known: bool = True) -> dict:
    """Scan message through safety scanner and return sanitized version."""
    result = safety_scan(text, sender, is_known)
    return {
        "safety_score": result["safety_score"],
        "risk_category": result["risk_category"],
        "threats": result["threats"],
        "is_blocked": result["is_blocked"],
        "text": result["sanitized_message"],
    }


def handle_whatsapp_reader(args: dict, **kw) -> str:
    """Handle whatsapp_reader tool calls."""
    action = str(args.get("action") or "").strip().lower()

    valid_actions = (
        "list_chats",
        "get_messages",
        "search_contacts",
        "get_contact_chats",
        "get_last_interaction",
        "get_message_context",
        "share_fact",
    )
    if action not in valid_actions:
        return _tool_error(
            f"Unknown action: {action}. Must be one of: {', '.join(valid_actions)}"
        )

    conn = None
    try:
        conn = _get_db()
        _ensure_schema(conn)
    except Exception as e:
        return _tool_error(f"Database connection failed: {e}")

    try:
        if action == "list_chats":
            return _list_chats(conn, args)
        elif action == "get_messages":
            return _get_messages(conn, args)
        elif action == "search_contacts":
            return _search_contacts(conn, args)
        elif action == "get_contact_chats":
            return _get_contact_chats(conn, args)
        elif action == "get_last_interaction":
            return _get_last_interaction(conn, args)
        elif action == "get_message_context":
            return _get_message_context(conn, args)
        elif action == "share_fact":
            return _share_fact(args)
    except FileNotFoundError as e:
        return _tool_error(str(e))
    except urllib.error.HTTPError as e:
        return _tool_error(f"Bridge API error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        return _tool_error(f"Bridge connection failed: {e.reason}")
    except Exception as e:
        return _tool_error(f"whatsapp_reader failed: {type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()


def _list_chats(conn: sqlite3.Connection, args: dict) -> str:
    limit = min(int(args.get("limit", 20)), 100)

    # Read from bridge's messages.db directly
    import os
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        rows = bridge_conn.execute(
            """
            SELECT jid, name, last_message_time
            FROM chats
            ORDER BY last_message_time DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

        chats = []
        for row in rows:
            # Determine if group by JID pattern
            jid = row["jid"]
            is_group = "@g.us" in jid

            chats.append({
                "jid": jid,
                "name": row["name"] or jid.replace("@s.whatsapp.net", "").replace("@g.us", ""),
                "is_group": is_group,
                "last_message_time": row["last_message_time"],
            })
    finally:
        bridge_conn.close()

    # Enrich with safety info and cache
    enriched = []
    for chat in chats:
        # Get last message for this chat
        last_msg_conn = sqlite3.connect(str(bridge_db))
        last_msg_conn.row_factory = sqlite3.Row
        try:
            last_row = last_msg_conn.execute(
                """
                SELECT sender, content, timestamp, is_from_me
                FROM messages
                WHERE chat_jid = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                [chat["jid"]],
            ).fetchone()

            last_message = last_row["content"] if last_row else ""
            last_sender = last_row["sender"] if last_row else ""
            last_time = last_row["timestamp"] if last_row else chat.get("last_message_time", "")
        finally:
            last_msg_conn.close()

        # Cache chat
        conn.execute(
            """
            INSERT OR REPLACE INTO whatsapp_chat_cache
            (jid, name, is_group, last_message_time, last_message, last_sender)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat.get("jid", ""),
                chat.get("name", ""),
                1 if chat.get("is_group") else 0,
                last_time,
                last_message,
                last_sender,
            ),
        )

        # Safety scan last message if present
        safety = _safe_message(last_message, last_sender) if last_message else None

        enriched.append({
            "jid": chat.get("jid"),
            "name": chat.get("name"),
            "is_group": chat.get("is_group", False),
            "last_message_time": last_time,
            "last_message": safety["text"] if safety else "",
            "last_message_safety": {
                "score": safety["safety_score"],
                "category": safety["risk_category"],
                "threats": safety["threats"],
            } if safety else None,
        })

    conn.commit()

    return _tool_result({
        "status": "ok",
        "chats": enriched,
        "count": len(enriched),
    })


def _get_messages(conn: sqlite3.Connection, args: dict) -> str:
    chat_jid = args.get("chat_jid")
    if not chat_jid:
        return _tool_error("chat_jid is required for get_messages")

    limit = min(int(args.get("limit", 20)), 100)
    min_safety = float(args.get("min_safety_score", 0.0))

    # Read from bridge's messages.db directly
    import os
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        rows = bridge_conn.execute(
            """
            SELECT id, chat_jid, sender, content as text, timestamp, is_from_me
            FROM messages
            WHERE chat_jid = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [chat_jid, limit],
        ).fetchall()

        messages = []
        for row in rows:
            messages.append({
                "id": row["id"],
                "chat_jid": row["chat_jid"],
                "sender": row["sender"],
                "sender_display": row["sender"],
                "text": row["text"] or "",
                "timestamp": row["timestamp"],
                "is_from_me": bool(row["is_from_me"]),
            })
    finally:
        bridge_conn.close()

    # Safety scan and cache
    safe_messages = []
    for msg in messages:
        text = msg.get("text", "")
        sender = msg.get("sender", "")
        is_from_me = msg.get("is_from_me", False)

        safety = _safe_message(text, sender, is_known=True)

        # Skip if below safety threshold
        if safety["safety_score"] < min_safety:
            continue

        # Cache message
        conn.execute(
            """
            INSERT OR REPLACE INTO whatsapp_message_cache
            (id, message_id, chat_jid, sender, sender_display, original_text, sanitized_text,
             safety_score, risk_category, threats, timestamp, is_from_me)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                msg.get("id", ""),
                chat_jid,
                sender,
                msg.get("sender_display", ""),
                text,
                safety["text"],
                safety["safety_score"],
                safety["risk_category"],
                json.dumps(safety["threats"]),
                msg.get("timestamp", ""),
                1 if is_from_me else 0,
            ),
        )

        safe_messages.append({
            "id": msg.get("id"),
            "sender": sender,
            "sender_display": msg.get("sender_display", ""),
            "text": safety["text"],
            "timestamp": msg.get("timestamp"),
            "is_from_me": is_from_me,
            "safety": {
                "score": safety["safety_score"],
                "category": safety["risk_category"],
                "threats": safety["threats"],
                "is_blocked": safety["is_blocked"],
            },
        })

    conn.commit()

    return _tool_result({
        "status": "ok",
        "chat_jid": chat_jid,
        "messages": safe_messages,
        "count": len(safe_messages),
        "filtered_count": len(messages) - len(safe_messages),
    })


def _search_contacts(conn: sqlite3.Connection, args: dict) -> str:
    query = args.get("query")
    if not query:
        return _tool_error("query is required for search_contacts")

    # Read from bridge's messages.db directly
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        # Search in chats table (name and jid)
        rows = bridge_conn.execute(
            """
            SELECT jid, name
            FROM chats
            WHERE name LIKE ? OR jid LIKE ?
            LIMIT 20
            """,
            [f"%{query}%", f"%{query}%"],
        ).fetchall()

        contacts = []
        for row in rows:
            jid = row["jid"]
            is_group = "@g.us" in jid
            phone = jid.replace("@s.whatsapp.net", "").replace("@g.us", "") if not is_group else None
            contacts.append({
                "jid": jid,
                "name": row["name"] or phone or jid,
                "phone": phone,
                "is_group": is_group,
            })
    finally:
        bridge_conn.close()

    return _tool_result({
        "status": "ok",
        "contacts": contacts,
        "count": len(contacts),
    })


def _get_contact_chats(conn: sqlite3.Connection, args: dict) -> str:
    phone = args.get("phone")
    if not phone:
        return _tool_error("phone is required for get_contact_chats")

    # Read from bridge's messages.db directly
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        rows = bridge_conn.execute(
            """
            SELECT jid, name, last_message_time
            FROM chats
            WHERE jid LIKE ?
            ORDER BY last_message_time DESC
            LIMIT 20
            """,
            [f"%{phone}%"],
        ).fetchall()

        chats = []
        for row in rows:
            jid = row["jid"]
            is_group = "@g.us" in jid
            chats.append({
                "jid": jid,
                "name": row["name"] or jid.replace("@s.whatsapp.net", ""),
                "is_group": is_group,
                "last_message_time": row["last_message_time"],
            })
    finally:
        bridge_conn.close()

    return _tool_result({
        "status": "ok",
        "phone": phone,
        "chats": chats,
        "count": len(chats),
    })


def _get_last_interaction(conn: sqlite3.Connection, args: dict) -> str:
    phone = args.get("phone")
    if not phone:
        return _tool_error("phone is required for get_last_interaction")

    # Read from bridge's messages.db directly
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        row = bridge_conn.execute(
            """
            SELECT m.id, m.chat_jid, m.sender, m.content as text, m.timestamp, m.is_from_me
            FROM messages m
            WHERE m.sender LIKE ? OR m.chat_jid LIKE ?
            ORDER BY m.timestamp DESC
            LIMIT 1
            """,
            [f"%{phone}%", f"%{phone}%"],
        ).fetchone()

        message = None
        if row:
            message = {
                "id": row["id"],
                "chat_jid": row["chat_jid"],
                "sender": row["sender"],
                "sender_display": row["sender"],
                "text": row["text"] or "",
                "timestamp": row["timestamp"],
                "is_from_me": bool(row["is_from_me"]),
            }
    finally:
        bridge_conn.close()

    if not message:
        return _tool_result({
            "status": "ok",
            "phone": phone,
            "message": None,
        })

    text = message.get("text", "")
    sender = message.get("sender", "")
    safety = _safe_message(text, sender)

    return _tool_result({
        "status": "ok",
        "phone": phone,
        "message": {
            "id": message.get("id"),
            "sender": sender,
            "text": safety["text"],
            "timestamp": message.get("timestamp"),
            "is_from_me": message.get("is_from_me", False),
            "safety": {
                "score": safety["safety_score"],
                "category": safety["risk_category"],
                "threats": safety["threats"],
            },
        },
    })


def _get_message_context(conn: sqlite3.Connection, args: dict) -> str:
    chat_jid = args.get("chat_jid")
    message_id = args.get("message_id")
    if not chat_jid or not message_id:
        return _tool_error("chat_jid and message_id are required for get_message_context")

    before = min(int(args.get("before", 5)), 50)
    after = min(int(args.get("after", 5)), 50)

    # Read from bridge's messages.db directly
    bridge_db = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
    if not bridge_db.exists():
        return _tool_error(f"WhatsApp bridge database not found at {bridge_db}")

    bridge_conn = sqlite3.connect(str(bridge_db))
    bridge_conn.row_factory = sqlite3.Row

    try:
        # Get the target message timestamp
        target = bridge_conn.execute(
            "SELECT timestamp FROM messages WHERE id = ? AND chat_jid = ?",
            [message_id, chat_jid],
        ).fetchone()

        if not target:
            return _tool_result({
                "status": "ok",
                "chat_jid": chat_jid,
                "target_message_id": message_id,
                "messages": [],
                "count": 0,
                "error": "Message not found",
            })

        target_time = target["timestamp"]

        # Get before messages
        before_rows = bridge_conn.execute(
            """
            SELECT id, chat_jid, sender, content as text, timestamp, is_from_me
            FROM messages
            WHERE chat_jid = ? AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [chat_jid, target_time, before],
        ).fetchall()

        # Get after messages
        after_rows = bridge_conn.execute(
            """
            SELECT id, chat_jid, sender, content as text, timestamp, is_from_me
            FROM messages
            WHERE chat_jid = ? AND timestamp > ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            [chat_jid, target_time, after],
        ).fetchall()

        # Get target message
        target_row = bridge_conn.execute(
            "SELECT id, chat_jid, sender, content as text, timestamp, is_from_me FROM messages WHERE id = ? AND chat_jid = ?",
            [message_id, chat_jid],
        ).fetchone()

        # Combine: before (reversed) + target + after
        all_rows = list(reversed(before_rows))
        if target_row:
            all_rows.append(target_row)
        all_rows.extend(after_rows)

        messages = []
        for row in all_rows:
            messages.append({
                "id": row["id"],
                "chat_jid": row["chat_jid"],
                "sender": row["sender"],
                "sender_display": row["sender"],
                "text": row["text"] or "",
                "timestamp": row["timestamp"],
                "is_from_me": bool(row["is_from_me"]),
            })
    finally:
        bridge_conn.close()

    # Safety scan all context messages
    safe_messages = []
    for msg in messages:
        text = msg.get("text", "")
        sender = msg.get("sender", "")
        is_from_me = msg.get("is_from_me", False)
        safety = _safe_message(text, sender)

        safe_messages.append({
            "id": msg.get("id"),
            "sender": sender,
            "text": safety["text"],
            "timestamp": msg.get("timestamp"),
            "is_from_me": is_from_me,
            "is_target": msg.get("id") == message_id,
            "safety": {
                "score": safety["safety_score"],
                "category": safety["risk_category"],
                "threats": safety["threats"],
            },
        })

    return _tool_result({
        "status": "ok",
        "chat_jid": chat_jid,
        "target_message_id": message_id,
        "messages": safe_messages,
        "count": len(safe_messages),
    })


def _share_fact(args: dict) -> str:
    fact = args.get("fact")
    if not fact:
        return _tool_error("fact is required for share_fact")

    domain = str(args.get("domain") or "communication").strip()

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
