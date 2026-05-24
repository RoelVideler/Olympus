"""WebSocket streaming for the Dashboard plugin.

Streams Zeus response chunks and system events to connected clients.
Uses aiohttp WebSocket support.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: Set[web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: web.WebSocketResponse) -> None:
        """Register a new WebSocket connection."""
        async with self._lock:
            self._connections.add(ws)
        logger.info("WebSocket connected (%d total)", len(self._connections))

    async def disconnect(self, ws: web.WebSocketResponse) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(ws)
        logger.info("WebSocket disconnected (%d total)", len(self._connections))

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        message = json.dumps(event)
        disconnected: List[web.WebSocketResponse] = []

        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_str(message)
                except Exception:
                    disconnected.append(ws)

        # Clean up dead connections
        for ws in disconnected:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global hub instance
_hub: Optional[WebSocketHub] = None


def get_hub() -> WebSocketHub:
    """Get or create the global WebSocket hub."""
    global _hub
    if _hub is None:
        _hub = WebSocketHub()
    return _hub


async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    """GET /ws — WebSocket endpoint for real-time streaming."""
    ws = web.WebSocketResponse(
        heartbeat=30,
        max_msg_size=1024 * 1024,  # 1MB
    )
    await ws.prepare(request)

    hub = get_hub()
    await hub.connect(ws)

    # Send connection confirmation
    await ws.send_json({
        "type": "connected",
        "timestamp": time.time(),
        "message": "Connected to Olympus Dashboard",
    })

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    # Handle client messages (e.g., subscriptions)
                    if data.get("type") == "subscribe":
                        await ws.send_json({
                            "type": "subscribed",
                            "channels": data.get("channels", ["*"]),
                        })
                    elif data.get("type") == "ping":
                        await ws.send_json({"type": "pong", "timestamp": time.time()})
                except json.JSONDecodeError:
                    await ws.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
            elif msg.type == WSMsgType.ERROR:
                logger.error("WebSocket error: %s", ws.exception())
                break
    finally:
        await hub.disconnect(ws)

    return ws


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
    """Stream a system event to all connected clients.

    Event types: profile_start, profile_stop, cron_executed, etc.
    """
    hub = get_hub()
    await hub.broadcast({
        "type": "system_event",
        "event_type": event_type,
        "data": data,
        "timestamp": time.time(),
    })


def register_websocket_route(app: web.Application) -> None:
    """Register the WebSocket route."""
    app.router.add_get("/ws", handle_websocket)
