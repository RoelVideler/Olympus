"""Profile lifecycle manager for Olympus Supervisor.

Starts, stops, and tracks profile processes via ``hermes -p <profile> -z``.
PID files stored in ``~/.hermes/supervisor/pids/``.
Reads ``run_mode`` from profile ``config.yaml`` files.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PID_DIR = Path.home() / ".hermes" / "supervisor" / "pids"
_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"

RUN_MODE_ALWAYS_ON = "always-on"
RUN_MODE_ON_DEMAND = "on-demand"
RUN_MODE_CRON_ONLY = "cron-only"


def _ensure_pid_dir() -> None:
    _PID_DIR.mkdir(parents=True, exist_ok=True)


def _validate_profile_name(profile: str) -> str:
    """Validate and return a safe profile name.

    Rejects names containing path separators, dots, or non-alphanumeric
    characters to prevent path traversal attacks.
    """
    if not profile:
        raise ValueError("profile name cannot be empty")
    if "/" in profile or "\\" in profile or ".." in profile:
        raise ValueError(f"invalid profile name: {profile!r} (path traversal not allowed)")
    if not profile.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"invalid profile name: {profile!r} (must be alphanumeric, hyphens, underscores)")
    return profile


def _pid_file(profile: str) -> Path:
    return _PID_DIR / f"{_validate_profile_name(profile)}.pid"


def _config_file(profile: str) -> Optional[Path]:
    _validate_profile_name(profile)
    candidate = _PROFILES_DIR / profile / "config.yaml"
    if candidate.is_file():
        return candidate
    return None


def _read_run_mode(profile: str) -> str:
    """Read run_mode from a profile's config.yaml. Defaults to on-demand."""
    cfg = _config_file(profile)
    if cfg is None:
        return RUN_MODE_ON_DEMAND
    try:
        import yaml
        with open(cfg) as f:
            data = yaml.safe_load(f)
        return (data or {}).get("run_mode", RUN_MODE_ON_DEMAND)
    except Exception:
        return RUN_MODE_ON_DEMAND


def _pid_alive(pid: int) -> bool:
    """Check if a process is alive (cross-platform safe)."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid(profile: str) -> Optional[int]:
    pf = _pid_file(profile)
    if not pf.is_file():
        return None
    try:
        data = json.loads(pf.read_text())
        pid = data.get("pid")
        if pid and _pid_alive(pid):
            return pid
    except Exception:
        pass
    pf.unlink(missing_ok=True)
    return None


def _write_pid(profile: str, pid: int) -> None:
    _ensure_pid_dir()
    data = {"pid": pid, "started_at": time.time(), "profile": profile}
    pf = _pid_file(profile)
    tmp = pf.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(pf)


def _clear_pid(profile: str) -> None:
    pf = _pid_file(profile)
    pf.unlink(missing_ok=True)


def start_profile(profile: str) -> Dict[str, Any]:
    """Start a profile process in the background.

    Launches ``hermes -p <profile>`` as a detached subprocess.
    Returns status dict with ok, pid, and profile keys.
    """
    existing = _read_pid(profile)
    if existing:
        return {"ok": False, "error": f"profile {profile} already running (pid {existing})"}

    try:
        proc = subprocess.Popen(
            ["hermes", "-p", profile, "gateway", "run"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "hermes CLI not found"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    _write_pid(profile, proc.pid)
    logger.info("Started profile %s (pid %d)", profile, proc.pid)
    return {"ok": True, "pid": proc.pid, "profile": profile}


def stop_profile(profile: str, *, reason: str = "requested") -> Dict[str, Any]:
    """Stop a profile process. Sends SIGTERM, waits, then SIGKILL."""
    pid = _read_pid(profile)
    if pid is None:
        return {"ok": False, "error": f"profile {profile} not running"}

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_pid(profile)
        return {"ok": True, "reason": reason, "profile": profile}

    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.5)

    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    _clear_pid(profile)
    logger.info("Stopped profile %s (pid %d, reason: %s)", profile, pid, reason)
    return {"ok": True, "reason": reason, "profile": profile, "pid": pid}


def get_profile_status(profile: str) -> Dict[str, Any]:
    """Return the current status of a profile."""
    pid = _read_pid(profile)
    run_mode = _read_run_mode(profile)

    if pid and _pid_alive(pid):
        return {
            "profile": profile,
            "status": "running",
            "pid": pid,
            "run_mode": run_mode,
        }

    if pid:
        return {
            "profile": profile,
            "status": "crashed",
            "pid": pid,
            "run_mode": run_mode,
        }

    return {
        "profile": profile,
        "status": "stopped",
        "pid": None,
        "run_mode": run_mode,
    }


def list_profiles() -> Dict[str, Dict[str, Any]]:
    """Return status for all known profiles."""
    results = {}
    if _PROFILES_DIR.is_dir():
        for d in sorted(_PROFILES_DIR.iterdir()):
            if d.is_dir() and (d / "config.yaml").is_file():
                results[d.name] = get_profile_status(d.name)
    return results
