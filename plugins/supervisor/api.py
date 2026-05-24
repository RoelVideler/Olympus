"""Lifecycle API for Olympus Supervisor.

Endpoints for Zeus to call: start_profile, stop_profile, health_check.
Returns process status for all managed profiles.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from . import lifecycle
from . import health
from . import idle

logger = logging.getLogger(__name__)


def start_profile(profile: str) -> Dict[str, Any]:
    """Start a profile process.

    Args:
        profile: Name of the profile to start.

    Returns:
        Dict with ok, pid, profile, and optional error keys.
    """
    result = lifecycle.start_profile(profile)
    if result.get("ok"):
        idle.record_activity(profile)
        logger.info("Zeus requested start of profile %s", profile)
    return result


def stop_profile(profile: str, *, reason: str = "requested") -> Dict[str, Any]:
    """Stop a profile process.

    Args:
        profile: Name of the profile to stop.
        reason: Reason for stopping (for logging).

    Returns:
        Dict with ok, profile, and optional error/pid keys.
    """
    result = lifecycle.stop_profile(profile, reason=reason)
    logger.info("Zeus requested stop of profile %s (reason: %s)", profile, reason)
    return result


def health_check(profile: str | None = None) -> Dict[str, Any]:
    """Check health of one or all profiles.

    Args:
        profile: Optional profile name. If None, returns all profiles.

    Returns:
        Dict with profile status information.
    """
    if profile:
        return lifecycle.get_profile_status(profile)
    return lifecycle.list_profiles()


def idle_status(profile: str | None = None) -> Dict[str, Any]:
    """Check idle status of one or all on-demand profiles.

    Args:
        profile: Optional profile name. If None, returns all on-demand profiles.

    Returns:
        Dict with idle timing information.
    """
    if profile:
        return idle.check_idle(profile)
    return idle.enforce_idle_ttl()


def enforce_idle() -> Dict[str, Dict[str, Any]]:
    """Force idle TTL enforcement on all on-demand profiles."""
    return idle.enforce_idle_ttl()


def get_profile_info(profile: str) -> Dict[str, Any]:
    """Get comprehensive info about a profile.

    Combines lifecycle status, idle info, and run_mode.

    Args:
        profile: Name of the profile.

    Returns:
        Dict with all available profile information.
    """
    status = lifecycle.get_profile_status(profile)
    idle_info = idle.check_idle(profile)
    return {
        **status,
        "idle": idle_info,
    }


def list_all() -> Dict[str, Dict[str, Any]]:
    """List all profiles with full status."""
    profiles = lifecycle.list_profiles()
    for name in profiles:
        idle_info = idle.check_idle(name)
        profiles[name]["idle"] = idle_info
    return profiles
