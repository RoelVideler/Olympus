# plugins/hermes/skills/gmail_triage.py
"""Gmail triage tool for Hermes.

Reads inbox, triages emails by urgency, drafts replies (never sends autonomously).
OAuth tokens stored at ~/.hermes/google/token.json with auto-refresh.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

TOKEN_PATH = Path.home() / ".hermes" / "google" / "token.json"
DB_PATH = Path.home() / ".hermes" / "olympus.db"

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

GMAIL_TRIAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "gmail_triage",
        "description": "Triage Gmail inbox, read emails, and draft replies. Never sends emails autonomously.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list_emails",
                        "read_email",
                        "draft_reply",
                        "draft_new",
                        "query_drafts",
                        "share_fact",
                    ],
                    "description": "Action to perform.",
                },
                "message_id": {
                    "type": "string",
                    "description": "Gmail message ID for read_email.",
                },
                "query": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Gmail search query (e.g., 'is:unread', 'from:boss@company.com', 'has:attachment').",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "description": "Maximum emails to return.",
                },
                "to": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Recipient email address (for draft_new).",
                },
                "subject": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Email subject (for drafts).",
                },
                "body": {
                    "type": "string",
                    "maxLength": 10000,
                    "description": "Email body content (for drafts).",
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "urgent", "friendly", "formal"],
                    "default": "professional",
                    "description": "Tone for drafted reply.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum draft results to return.",
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

_URGENT_KEYWORDS = [
    "urgent", "asap", "immediately", "emergency", "critical",
    "deadline", "overdue", "action required", "please respond",
    "time sensitive", "expiring", "final notice",
]

_IMPORTANT_SENDERS = []  # Populated from share_knowledge or config

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
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schema" / "001_gmail_triage.sql"
    if schema_path.exists():
        with open(schema_path) as f:
            conn.executescript(f.read())


def _load_tokens() -> dict:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"Google OAuth token not found at {TOKEN_PATH}. Run OAuth authorization first.")
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
    # Check if token is expired (with 5-min buffer)
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


def _gmail_request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    access_token = _get_access_token()
    url = f"{GMAIL_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    if body:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token expired, try refresh
            tokens = _load_tokens()
            new_tokens = _refresh_access_token(tokens["refresh_token"])
            new_tokens["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)
            _save_tokens(new_tokens)
            # Retry with new token
            headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        raise


def _triage_score(snippet: str, sender: str, subject: str) -> tuple[float, str]:
    text = f"{snippet} {subject}".lower()
    sender_lower = sender.lower()

    for kw in _URGENT_KEYWORDS:
        if kw in text:
            return 0.9, "urgent"

    if any(domain in sender_lower for domain in ["bank", "billing", "invoice", "payment"]):
        return 0.7, "financial"

    if any(domain in sender_lower for domain in ["noreply", "no-reply", "notification", "alert"]):
        return 0.2, "automated"

    if "@" in sender:
        return 0.5, "normal"

    return 0.3, "unknown"


def _get_message_detail(message_id: str) -> dict:
    return _gmail_request(f"/users/me/messages/{message_id}?format=full")


def _extract_headers(payload: dict) -> dict:
    headers = {}
    for h in payload.get("headers", []):
        headers[h["name"].lower()] = h["value"]
    return headers


def _extract_body(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "body" in part:
                import base64
                data = part["body"].get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        # Fallback to first part with body
        for part in payload["parts"]:
            if "body" in part and part["body"].get("data"):
                import base64
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    elif "body" in payload:
        import base64
        data = payload["body"].get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def _create_draft(to: str, subject: str, body: str, thread_id: str | None = None) -> dict:
    import base64
    message_lines = [
        f"To: {to}",
        f"Subject: {subject}",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
    ]
    raw_message = "\r\n".join(message_lines)
    raw_b64 = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("utf-8")

    draft_body = {"message": {"raw": raw_b64}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    return _gmail_request("/users/me/drafts", method="POST", body=draft_body)


def handle_gmail_triage(args: dict, **kw) -> str:
    """Handle gmail_triage tool calls."""
    action = str(args.get("action") or "").strip().lower()

    valid_actions = (
        "list_emails",
        "read_email",
        "draft_reply",
        "draft_new",
        "query_drafts",
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
        if action == "list_emails":
            return _list_emails(conn, args)
        elif action == "read_email":
            return _read_email(conn, args)
        elif action == "draft_reply":
            return _draft_reply(conn, args)
        elif action == "draft_new":
            return _draft_new(conn, args)
        elif action == "query_drafts":
            return _query_drafts(conn, args)
        elif action == "share_fact":
            return _share_fact(args)
    except FileNotFoundError as e:
        return _tool_error(str(e))
    except Exception as e:
        return _tool_error(f"gmail_triage failed: {type(e).__name__}: {e}")
    finally:
        if conn is not None:
            conn.close()


def _list_emails(conn: sqlite3.Connection, args: dict) -> str:
    query = args.get("query", "is:unread")
    max_results = min(int(args.get("max_results", 20)), 50)

    params = urllib.parse.urlencode({
        "q": query,
        "maxResults": max_results,
    })
    result = _gmail_request(f"/users/me/messages?{params}")

    messages = result.get("messages", [])
    if not messages:
        return _tool_result({"status": "ok", "emails": [], "count": 0, "query": query})

    emails = []
    for msg in messages:
        try:
            detail = _gmail_request(f"/users/me/messages/{msg['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date")
            headers = _extract_headers(detail.get("payload", {}))
            snippet = detail.get("snippet", "")
            sender = headers.get("from", "Unknown")
            subject = headers.get("subject", "(no subject)")
            received_at = headers.get("date", "")

            score, category = _triage_score(snippet, sender, subject)

            # Cache in DB
            conn.execute(
                """
                INSERT OR REPLACE INTO gmail_triage_cache
                (id, message_id, thread_id, sender, subject, snippet, received_at, labels, is_important, triage_score, triage_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    msg["id"],
                    detail.get("threadId", ""),
                    sender,
                    subject,
                    snippet,
                    received_at,
                    json.dumps(detail.get("labelIds", [])),
                    1 if score >= 0.7 else 0,
                    score,
                    category,
                ),
            )

            emails.append({
                "message_id": msg["id"],
                "thread_id": detail.get("threadId", ""),
                "sender": sender,
                "subject": subject,
                "snippet": snippet[:200],
                "triage_score": round(score, 2),
                "triage_category": category,
                "is_important": score >= 0.7,
            })
        except Exception:
            continue

    conn.commit()

    # Sort by triage score desc
    emails.sort(key=lambda e: e["triage_score"], reverse=True)

    urgent_count = sum(1 for e in emails if e["triage_category"] == "urgent")

    return _tool_result({
        "status": "ok",
        "emails": emails,
        "count": len(emails),
        "urgent_count": urgent_count,
        "query": query,
    })


def _read_email(conn: sqlite3.Connection, args: dict) -> str:
    message_id = args.get("message_id")
    if not message_id:
        return _tool_error("message_id is required for read_email")

    detail = _get_message_detail(message_id)
    payload = detail.get("payload", {})
    headers = _extract_headers(payload)
    body = _extract_body(payload)

    sender = headers.get("from", "Unknown")
    subject = headers.get("subject", "(no subject)")
    received_at = headers.get("date", "")
    to = headers.get("to", "")

    # Cache in DB
    conn.execute(
        """
        INSERT OR REPLACE INTO gmail_triage_cache
        (id, message_id, thread_id, sender, subject, snippet, received_at, labels, is_important, triage_score, triage_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            message_id,
            detail.get("threadId", ""),
            sender,
            subject,
            body[:200],
            received_at,
            json.dumps(detail.get("labelIds", [])),
            0,
            0.5,
            "read",
        ),
    )
    conn.commit()

    return _tool_result({
        "status": "ok",
        "message_id": message_id,
        "thread_id": detail.get("threadId", ""),
        "sender": sender,
        "to": to,
        "subject": subject,
        "date": received_at,
        "body": body[:5000],  # Limit body length
        "labels": detail.get("labelIds", []),
    })


def _draft_reply(conn: sqlite3.Connection, args: dict) -> str:
    message_id = args.get("message_id")
    if not message_id:
        return _tool_error("message_id is required for draft_reply")

    body = args.get("body")
    if not body:
        return _tool_error("body is required for draft_reply")

    # Get original message for context
    detail = _get_message_detail(message_id)
    payload = detail.get("payload", {})
    headers = _extract_headers(payload)

    sender = headers.get("from", "Unknown")
    subject = headers.get("subject", "(no subject)")
    thread_id = detail.get("threadId")

    # Add Re: prefix if not present
    if not subject.startswith("Re:"):
        subject = f"Re: {subject}"

    # Extract original sender email for reply-to
    import re
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
    to_address = email_match.group(0) if email_match else sender

    draft = _create_draft(to=to_address, subject=subject, body=body, thread_id=thread_id)

    # Log the draft
    draft_id = draft.get("id", "unknown")
    conn.execute(
        """
        INSERT INTO gmail_sent_log (id, to_recipients, subject, thread_id)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), to_address, subject, thread_id),
    )
    conn.commit()

    return _tool_result({
        "status": "drafted",
        "draft_id": draft_id,
        "to": to_address,
        "subject": subject,
        "thread_id": thread_id,
        "note": "Draft saved in Gmail. Review and send manually.",
    })


def _draft_new(conn: sqlite3.Connection, args: dict) -> str:
    to = args.get("to")
    subject = args.get("subject")
    body = args.get("body")

    if not to:
        return _tool_error("to is required for draft_new")
    if not subject:
        return _tool_error("subject is required for draft_new")
    if not body:
        return _tool_error("body is required for draft_new")

    draft = _create_draft(to=to, subject=subject, body=body)

    draft_id = draft.get("id", "unknown")
    conn.execute(
        """
        INSERT INTO gmail_sent_log (id, to_recipients, subject)
        VALUES (?, ?, ?)
        """,
        (str(uuid.uuid4()), to, subject),
    )
    conn.commit()

    return _tool_result({
        "status": "drafted",
        "draft_id": draft_id,
        "to": to,
        "subject": subject,
        "note": "Draft saved in Gmail. Review and send manually.",
    })


def _query_drafts(conn: sqlite3.Connection, args: dict) -> str:
    limit = min(int(args.get("limit", 20)), 100)

    rows = conn.execute(
        """
        SELECT id, to_recipients, cc_recipients, subject, sent_at, thread_id, created_at
        FROM gmail_sent_log
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return _tool_result({
        "status": "ok",
        "drafts": [
            {
                "id": row["id"],
                "to": row["to_recipients"],
                "cc": row["cc_recipients"],
                "subject": row["subject"],
                "created_at": row["created_at"],
                "thread_id": row["thread_id"],
            }
            for row in rows
        ],
        "count": len(rows),
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
