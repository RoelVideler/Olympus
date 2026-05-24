"""Dashboard platform adapter — Hermes gateway plugin for the Olympus web dashboard.

Serves REST, GraphQL, and WebSocket endpoints for viewing agent data
from the shared SQLite database. Uses aiohttp (already a Hermes dependency).

Endpoints:
- GET  /api/health      — system health data
- GET  /api/wiki        — wiki/knowledge entries
- GET  /api/calendar    — calendar events
- GET  /api/contacts    — contact list
- GET  /api/preferences — user preferences
- POST /api/graphql     — complex multi-type queries
- POST /api/login       — session authentication
- GET  /ws              — WebSocket for real-time streaming
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import web

from .auth import auth_middleware
from .api import register_routes
from .graphql import register_graphql_route
from .websocket import register_websocket_route

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8080
DEFAULT_HOST = "127.0.0.1"

_app: Optional[web.Application] = None
_runner: Optional[web.AppRunner] = None
_site: Optional[web.TCPSite] = None
_init_lock = threading.Lock()


def _create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application(middlewares=[auth_middleware])

    # Register all routes
    register_routes(app)
    register_graphql_route(app)
    register_websocket_route(app)

    # Static files (if a frontend build exists)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.router.add_static("/static/", path=static_dir, name="static")
        app.router.add_get("/", lambda r: web.FileResponse(os.path.join(static_dir, "index.html")))

    return app


def _get_port() -> int:
    """Get the configured port from env or default."""
    try:
        return int(os.getenv("DASHBOARD_PORT", str(DEFAULT_PORT)))
    except ValueError:
        return DEFAULT_PORT


def _get_host() -> str:
    """Get the configured host from env or default."""
    return os.getenv("DASHBOARD_HOST", DEFAULT_HOST)


async def _start_server(app: web.Application) -> None:
    """Start the aiohttp server."""
    global _runner, _site

    host = _get_host()
    port = _get_port()

    _runner = web.AppRunner(app)
    await _runner.setup()
    _site = web.TCPSite(_runner, host, port)
    await _site.start()

    logger.info("Dashboard serving at http://%s:%d", host, port)


async def _stop_server() -> None:
    """Stop the aiohttp server."""
    global _runner, _site

    if _site:
        await _site.stop()
        _site = None
    if _runner:
        await _runner.cleanup()
        _runner = None

    logger.info("Dashboard server stopped")


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system at startup.

    Registers the Dashboard as a gateway platform adapter.
    """
    global _app

    with _init_lock:
        if _app is not None:
            return

        _app = _create_app()

        # Start the server in a background task via the gateway event loop
        try:
            loop = ctx.get_event_loop()
            loop.create_task(_start_server(_app))
        except Exception:
            # Fallback: if we can't get the event loop, log and continue
            logger.warning(
                "Could not get gateway event loop — dashboard will not auto-start. "
                "Use DASHBOARD_PORT=%d manually.",
                _get_port(),
            )

        logger.info("Dashboard plugin registered")


def get_app() -> Optional[web.Application]:
    """Get the aiohttp application (for testing)."""
    return _app
