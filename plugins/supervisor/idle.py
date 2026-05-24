"""Idle TTL handler for Olympus Supervisor.

Tracks last activity timestamp per on-demand profile.
Kills profiles that exceed their idle TTL (default 5 minutes).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from . import lifecycle

logger = logging.getLogger(__name__)

DEFAULT_IDLE_TTL = 300  # 5 minutes
_STATE_FILE = Path.home() / ".hermes" / "supervisor" / "idle_state.json"
_LOCK = threading.Lock()


def _ensure_state_dir() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> Dict[str, Any]:
    if _STATE_FILE.is_file():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    _ensure_state_dir()
    tmp = _STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(_STATE_FILE)


def record_activity(profile: str) -> None:
    """Record that a profile had activity (resets idle timer)."""
    with _LOCK:
        state = _load_state()
        state[profile] = {"last_activity": time.time()}
        _save_state(state)


def get_idle_time(profile: str) -> Optional[float]:
    """Return seconds since last activity, or None if never recorded."""
    with _LOCK:
        state = _load_state()
        entry = state.get(profile)
        if entry:
            return time.time() - entry.get("last_activity", 0)
    return None


def get_ttl_for_profile(profile: str) -> int:
    """Return the idle TTL for a profile. Reads from config if available."""
    cfg = lifecycle._config_file(profile)
    if cfg:
        try:
            import yaml
            with open(cfg) as f:
                data = yaml.safe_load(f)
            idle_ttl = (data or {}).get("idle_ttl")
            if idle_ttl:
                return int(idle_ttl)
        except Exception:
            pass
    return DEFAULT_IDLE_TTL


def check_idle(profile: str) -> Dict[str, Any]:
    """Check if a profile has exceeded its idle TTL.

    Returns dict with profile, idle_seconds, ttl, and exceeded flag.
    """
    idle_time = get_idle_time(profile)
    ttl = get_ttl_for_profile(profile)

    if idle_time is None:
        return {"profile": profile, "idle_seconds": None, "ttl": ttl, "exceeded": False}

    exceeded = idle_time > ttl
    return {
        "profile": profile,
        "idle_seconds": round(idle_time, 1),
        "ttl": ttl,
        "exceeded": exceeded,
    }


def enforce_idle_ttl() -> Dict[str, Dict[str, Any]]:
    """Check all on-demand profiles and kill those exceeding idle TTL.

    Returns dict of profile -> enforcement result.
    """
    results = {}
    statuses = lifecycle.list_profiles()

    for profile, info in statuses.items():
        if info.get("run_mode") != lifecycle.RUN_MODE_ON_DEMAND:
            continue

        idle_check = check_idle(profile)
        if idle_check["exceeded"]:
            stop_result = lifecycle.stop_profile(profile, reason="idle timeout")
            results[profile] = {
                "action": "stopped",
                "idle_seconds": idle_check["idle_seconds"],
                "ttl": idle_check["ttl"],
                "stop_result": stop_result,
            }
            logger.info(
                "Killed idle profile %s (idle=%.0fs, ttl=%ds)",
                profile, idle_check["idle_seconds"], idle_check["ttl"],
            )
        else:
            results[profile] = {
                "action": "ok",
                "idle_seconds": idle_check["idle_seconds"],
                "ttl": idle_check["ttl"],
            }

    return results


class IdleEnforcer:
    """Background thread that enforces idle TTL for on-demand profiles."""

    def __init__(self, check_interval: int = 60):
        self._interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True, name="supervisor-idle")
            self._thread.start()
            logger.info("Idle enforcer started (interval=%ds)", self._interval)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
            logger.info("Idle enforcer stopped")

    def _run(self) -> None:
        while self._running:
            try:
                enforce_idle_ttl()
            except Exception as exc:
                logger.error("Idle enforcement error: %s", exc)
            time.sleep(self._interval)
