"""Health monitor for Olympus Supervisor.

Periodically checks if profile processes are alive.
Detects crashes and restarts always-on profiles.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from . import lifecycle

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL = 30


class HealthMonitor:
    """Background thread that monitors profile health."""

    def __init__(
        self,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        on_crash: Optional[Callable[[str], None]] = None,
    ):
        self._interval = check_interval
        self._on_crash = on_crash or self._default_restart
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _default_restart(self, profile: str) -> None:
        result = lifecycle.start_profile(profile)
        if result.get("ok"):
            logger.info("Auto-restarted crashed profile %s (pid %d)", profile, result["pid"])
        else:
            logger.error("Failed to restart crashed profile %s: %s", profile, result.get("error"))

    def start(self) -> None:
        """Start the health monitor background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True, name="supervisor-health")
            self._thread.start()
            logger.info("Health monitor started (interval=%ds)", self._interval)

    def stop(self) -> None:
        """Stop the health monitor."""
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
            logger.info("Health monitor stopped")

    def _run(self) -> None:
        while self._running:
            try:
                self._check_all()
            except Exception as exc:
                logger.error("Health check error: %s", exc)
            time.sleep(self._interval)

    def _check_all(self) -> None:
        statuses = lifecycle.list_profiles()
        for profile, info in statuses.items():
            if info["status"] == "crashed":
                run_mode = info.get("run_mode", "on-demand")
                if run_mode == lifecycle.RUN_MODE_ALWAYS_ON:
                    logger.warning("Profile %s crashed — restarting (always-on)", profile)
                    self._on_crash(profile)
                else:
                    logger.debug("Profile %s crashed — not restarting (run_mode=%s)", profile, run_mode)
                    lifecycle._clear_pid(profile)

    def check_profile(self, profile: str) -> Dict[str, Any]:
        """Run a single health check for a profile."""
        return lifecycle.get_profile_status(profile)

    def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health checks for all profiles."""
        return lifecycle.list_profiles()
