#!/usr/bin/env python3
"""WhatsApp webhook receiver with smart buffering and safety scanning.

Receives real-time messages from WhatsApp bridge, buffers them with
intelligent grouping (typing detection, timeouts), then triggers
safety scanning and forwards to Hermes.

Buffer logic:
- Message received → start 10s timer
- Typing detected → wait for message or 15s typing timeout
- Max timeout: 5 minutes (forces scan regardless)
- On trigger → batch scan → forward to Hermes
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/Users/roelvideler/openspec/Olympus")

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock

from plugins.hermes.skills.whatsapp_safety import scan_message as safety_scan

# Configuration
WEBHOOK_PORT = 8769
BRIDGE_DB = Path.home() / "openspec" / "whatsapp-mcp" / "whatsapp-bridge" / "store" / "messages.db"
OLYMPUS_DB = Path.home() / ".hermes" / "olympus.db"
SAFETY_LOG = Path.home() / ".hermes" / "whatsapp" / "safety-log.json"

# Timing constants (seconds)
MESSAGE_BUFFER_SECONDS = 10
TYPING_TIMEOUT_SECONDS = 15
MAX_BUFFER_SECONDS = 300  # 5 minutes


class ChatBuffer:
    """Manages buffered messages for a single chat with state machine."""

    def __init__(self, chat_jid: str):
        self.chat_jid = chat_jid
        self.messages: List[Dict[str, Any]] = []
        self.is_typing = False
        self.last_activity = time.time()
        self.timer_started = time.time()
        self.triggered = False
        self.lock = Lock()

    def add_message(self, message: Dict[str, Any]) -> None:
        with self.lock:
            self.messages.append(message)
            self.is_typing = False
            self.last_activity = time.time()

            if not self.triggered:
                self.timer_started = time.time()

    def set_typing(self, is_typing: bool) -> None:
        with self.lock:
            self.is_typing = is_typing
            self.last_activity = time.time()

    def should_trigger(self) -> bool:
        """Check if buffer should be processed."""
        with self.lock:
            if self.triggered or not self.messages:
                return False

            elapsed = time.time() - self.timer_started

            # Max timeout
            if elapsed >= MAX_BUFFER_SECONDS:
                return True

            # Message buffer timeout
            if elapsed >= MESSAGE_BUFFER_SECONDS and not self.is_typing:
                return True

            # Typing timeout
            if self.is_typing and (time.time() - self.last_activity) >= TYPING_TIMEOUT_SECONDS:
                return True

            return False

    def drain(self) -> List[Dict[str, Any]]:
        """Get and clear buffered messages."""
        with self.lock:
            self.triggered = True
            messages = self.messages.copy()
            self.messages.clear()
            return messages


class BufferManager:
    """Manages buffers for all active chats."""

    def __init__(self):
        self.buffers: Dict[str, ChatBuffer] = {}
        self.lock = Lock()

    def get_buffer(self, chat_jid: str) -> ChatBuffer:
        with self.lock:
            if chat_jid not in self.buffers:
                self.buffers[chat_jid] = ChatBuffer(chat_jid)
            return self.buffers[chat_jid]

    def cleanup(self) -> None:
        """Remove empty buffers."""
        with self.lock:
            empty = [jid for jid, buf in self.buffers.items() if not buf.messages and buf.triggered]
            for jid in empty:
                del self.buffers[jid]


buffer_manager = BufferManager()


def scan_and_log(messages: List[Dict[str, Any]], chat_jid: str) -> List[Dict[str, Any]]:
    """Scan messages through safety scanner and log results."""
    results = []
    for msg in messages:
        content = msg.get("content", "")
        if not content:
            continue

        sender = msg.get("sender", "unknown")
        result = safety_scan(content, sender, is_known_sender=True)

        results.append({
            "message_id": msg.get("id"),
            "chat_jid": chat_jid,
            "sender": sender,
            "timestamp": msg.get("timestamp"),
            "content_preview": content[:100],
            "safety_score": result["safety_score"],
            "risk_category": result["risk_category"],
            "threats": result["threats"],
            "is_blocked": result["is_blocked"],
            "sanitized_text": result["sanitized_message"],
        })

    # Log to safety log
    SAFETY_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if SAFETY_LOG.exists():
        try:
            with open(SAFETY_LOG) as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            existing = []

    existing.extend(results)
    existing = existing[-1000:]

    with open(SAFETY_LOG, "w") as f:
        json.dump(existing, f, indent=2)

    return results


def forward_to_hermes(chat_jid: str, scan_results: List[Dict[str, Any]]) -> None:
    """Forward scanned messages to Hermes for processing."""
    # For now, log to Olympus DB
    # In future, this could call Hermes API or write to a queue
    conn = sqlite3.connect(str(OLYMPUS_DB))
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hermes_inbox (
                id TEXT PRIMARY KEY,
                chat_jid TEXT,
                sender TEXT,
                content TEXT,
                safety_score REAL,
                risk_category TEXT,
                threats TEXT,
                processed_at TEXT DEFAULT (datetime('now'))
            )
        """)

        for result in scan_results:
            conn.execute(
                """
                INSERT INTO hermes_inbox
                (id, chat_jid, sender, content, safety_score, risk_category, threats)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{chat_jid}_{result['message_id']}_{int(time.time())}",
                    chat_jid,
                    result["sender"],
                    result["sanitized_text"],
                    result["safety_score"],
                    result["risk_category"],
                    json.dumps(result["threats"]),
                ),
            )

        conn.commit()
        print(f"[{datetime.now(timezone.utc).isoformat()}] Forwarded {len(scan_results)} message(s) to Hermes inbox for {chat_jid}")

        # Print alerts for high-risk messages
        alerts = [r for r in scan_results if r["safety_score"] < 0.6]
        if alerts:
            print(f"  ⚠️  {len(alerts)} high-risk message(s) detected:")
            for alert in alerts:
                print(f"    From: {alert['sender']}, Score: {alert['safety_score']}, Threats: {alert['threats']}")

    finally:
        conn.close()


def process_buffer(chat_jid: str) -> None:
    """Process a chat buffer: scan and forward."""
    buffer = buffer_manager.get_buffer(chat_jid)
    messages = buffer.drain()

    if not messages:
        return

    print(f"[{datetime.now(timezone.utc).isoformat()}] Processing buffer for {chat_jid} ({len(messages)} message(s))")

    scan_results = scan_and_log(messages, chat_jid)
    forward_to_hermes(chat_jid, scan_results)


def buffer_monitor_loop() -> None:
    """Background thread that monitors buffers for timeout triggers."""
    while True:
        try:
            # Copy buffer list to avoid holding lock during processing
            with buffer_manager.lock:
                active_buffers = list(buffer_manager.buffers.items())

            for chat_jid, buffer in active_buffers:
                if buffer.should_trigger():
                    process_buffer(chat_jid)

            buffer_manager.cleanup()
        except Exception as e:
            print(f"[ERROR] Buffer monitor error: {e}")

        time.sleep(1)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for WhatsApp bridge webhook."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        if self.path == "/whatsapp/webhook":
            self._handle_message(data)
        elif self.path == "/whatsapp/typing":
            self._handle_typing(data)
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming message webhook."""
        chat_jid = data.get("chat_jid")
        if not chat_jid:
            return

        message = {
            "id": data.get("id"),
            "sender": data.get("sender"),
            "content": data.get("content", ""),
            "timestamp": data.get("timestamp"),
            "is_from_me": data.get("is_from_me", False),
        }

        # Skip own messages
        if message["is_from_me"]:
            return

        buffer = buffer_manager.get_buffer(chat_jid)
        buffer.add_message(message)

        print(f"[{datetime.now(timezone.utc).isoformat()}] Message buffered for {chat_jid} from {message['sender']}")

    def _handle_typing(self, data: Dict[str, Any]) -> None:
        """Handle typing indicator webhook."""
        chat_jid = data.get("chat_jid")
        if not chat_jid:
            return

        is_typing = data.get("is_typing", False)
        buffer = buffer_manager.get_buffer(chat_jid)
        buffer.set_typing(is_typing)

        if is_typing:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Typing started for {chat_jid}")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Typing stopped for {chat_jid}")

    def log_message(self, format, *args):
        pass  # Suppress default logging


def main() -> None:
    """Start the webhook server and buffer monitor."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting WhatsApp webhook receiver on port {WEBHOOK_PORT}")

    # Start buffer monitor thread
    monitor = Thread(target=buffer_monitor_loop, daemon=True)
    monitor.start()

    # Start webhook server
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    print(f"Webhook server running on http://0.0.0.0:{WEBHOOK_PORT}")
    print(f"  Message endpoint: POST /whatsapp/webhook")
    print(f"  Typing endpoint: POST /whatsapp/typing")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
