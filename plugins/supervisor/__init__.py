"""Supervisor plugin — profile lifecycle management for Olympus.

Hermes v0.14.0 does not have a gateway extension API for process lifecycle
management, so Supervisor operates as a standalone plugin that manages
processes directly via subprocess.

Registers tools for Zeus to call: start_profile, stop_profile, health_check.
Starts background threads for health monitoring and idle TTL enforcement.
Auto-starts always-on profiles on registration.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict

from . import lifecycle
from . import health
from . import idle
from . import api

logger = logging.getLogger(__name__)

_monitor: health.HealthMonitor | None = None
_enforcer: idle.IdleEnforcer | None = None
_init_lock = threading.Lock()


_START_PROFILE_SCHEMA = {
    "name": "start_profile",
    "description": "Start an Olympus profile process. Use for on-demand profiles or to restart a stopped profile.",
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Name of the profile to start (e.g. chronos, iaso, plutus).",
            },
        },
        "required": ["profile"],
    },
}

_STOP_PROFILE_SCHEMA = {
    "name": "stop_profile",
    "description": "Stop a running Olympus profile process.",
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Name of the profile to stop.",
            },
            "reason": {
                "type": "string",
                "description": "Reason for stopping the profile.",
                "default": "requested",
            },
        },
        "required": ["profile"],
    },
}

_HEALTH_CHECK_SCHEMA = {
    "name": "health_check",
    "description": "Check health status of Olympus profiles. Returns running, stopped, or crashed status.",
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Optional profile name. If omitted, returns status for all profiles.",
            },
        },
    },
}

_IDLE_STATUS_SCHEMA = {
    "name": "idle_status",
    "description": "Check idle time for on-demand profiles. Shows how long since last activity.",
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Optional profile name. If omitted, returns idle status for all on-demand profiles.",
            },
        },
    },
}


def _handle_start_profile(args: dict, **kw) -> Dict[str, Any]:
    return api.start_profile(args.get("profile", ""))


def _handle_stop_profile(args: dict, **kw) -> Dict[str, Any]:
    return api.stop_profile(args.get("profile", ""), reason=args.get("reason", "requested"))


def _handle_health_check(args: dict, **kw) -> Dict[str, Any]:
    profile = args.get("profile")
    return api.health_check(profile if profile else None)


def _handle_idle_status(args: dict, **kw) -> Dict[str, Any]:
    profile = args.get("profile")
    return api.idle_status(profile if profile else None)


def _auto_start_always_on() -> None:
    """Start all always-on profiles."""
    profiles = lifecycle.list_profiles()
    for name, info in profiles.items():
        if info.get("run_mode") == lifecycle.RUN_MODE_ALWAYS_ON:
            if info.get("status") != "running":
                result = lifecycle.start_profile(name)
                if result.get("ok"):
                    logger.info("Auto-started always-on profile %s (pid %d)", name, result["pid"])
                else:
                    logger.error("Failed to auto-start profile %s: %s", name, result.get("error"))


def register(ctx) -> None:
    """Register the Supervisor plugin.

    Hermes v0.14.0 has no gateway extension API for process lifecycle,
    so we register as a standalone plugin with tools.
    """
    global _monitor, _enforcer

    with _init_lock:
        if _monitor is not None:
            return

        ctx.register_tool(
            name="start_profile",
            toolset="supervisor",
            schema=_START_PROFILE_SCHEMA,
            handler=_handle_start_profile,
            description="Start an Olympus profile process.",
        )

        ctx.register_tool(
            name="stop_profile",
            toolset="supervisor",
            schema=_STOP_PROFILE_SCHEMA,
            handler=_handle_stop_profile,
            description="Stop a running Olympus profile process.",
        )

        ctx.register_tool(
            name="health_check",
            toolset="supervisor",
            schema=_HEALTH_CHECK_SCHEMA,
            handler=_handle_health_check,
            description="Check health status of Olympus profiles.",
        )

        ctx.register_tool(
            name="idle_status",
            toolset="supervisor",
            schema=_IDLE_STATUS_SCHEMA,
            handler=_handle_idle_status,
            description="Check idle time for on-demand profiles.",
        )

        _monitor = health.HealthMonitor()
        _monitor.start()

        _enforcer = idle.IdleEnforcer()
        _enforcer.start()

        _auto_start_always_on()

        logger.info("Supervisor plugin registered")
