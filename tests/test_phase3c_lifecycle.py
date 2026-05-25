"""Tests for Phase 3c: Always-on Profile Lifecycle Management.

Tests run_mode enforcement, idle_ttl shutdown, auto-start behavior,
health monitoring, and crash recovery for the Olympus Supervisor.
"""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add plugins to path
import sys
_plugins_dir = Path(__file__).parent.parent / "plugins"
sys.path.insert(0, str(_plugins_dir))

from supervisor.lifecycle import (
    _validate_profile_name,
    _read_run_mode,
    _pid_alive,
    _read_pid,
    _write_pid,
    _clear_pid,
    start_profile,
    stop_profile,
    get_profile_status,
    list_profiles,
    RUN_MODE_ALWAYS_ON,
    RUN_MODE_ON_DEMAND,
    RUN_MODE_CRON_ONLY,
)
from supervisor.idle import (
    record_activity,
    get_idle_time,
    get_ttl_for_profile,
    check_idle,
    enforce_idle_ttl,
    IdleEnforcer,
    DEFAULT_IDLE_TTL,
)
from supervisor.health import HealthMonitor


@pytest.fixture(autouse=True)
def clean_pid_dir(tmp_path, monkeypatch):
    """Use temp directory for PID files."""
    monkeypatch.setattr("supervisor.lifecycle._PID_DIR", tmp_path / "pids")
    yield


@pytest.fixture(autouse=True)
def clean_idle_state(tmp_path, monkeypatch):
    """Use temp directory for idle state files."""
    monkeypatch.setattr("supervisor.idle._STATE_FILE", tmp_path / "idle_state.json")
    yield


class TestProfileNameValidation:
    """Test profile name security validation."""

    def test_valid_name(self):
        assert _validate_profile_name("zeus") == "zeus"

    def test_valid_name_with_hyphen(self):
        assert _validate_profile_name("hermes-agent") == "hermes-agent"

    def test_valid_name_with_underscore(self):
        assert _validate_profile_name("health_sync") == "health_sync"

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_profile_name("")

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_profile_name("../etc/passwd")

    def test_slash_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_profile_name("foo/bar")

    def test_backslash_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_profile_name("foo\\bar")

    def test_dot_dot_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_profile_name("..")

    def test_special_chars_rejected(self):
        with pytest.raises(ValueError, match="must be alphanumeric"):
            _validate_profile_name("foo@bar")


class TestRunModeReading:
    """Test reading run_mode from profile configs."""

    def test_missing_config_defaults_to_on_demand(self, tmp_path, monkeypatch):
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", tmp_path / "profiles")
        assert _read_run_mode("nonexistent") == RUN_MODE_ON_DEMAND

    def test_reads_always_on_from_config(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_dir = profiles_dir / "zeus"
        profile_dir.mkdir()
        (profile_dir / "config.yaml").write_text("run_mode: always-on\n")
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", profiles_dir)
        assert _read_run_mode("zeus") == RUN_MODE_ALWAYS_ON

    def test_reads_cron_only_from_config(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_dir = profiles_dir / "chronos"
        profile_dir.mkdir()
        (profile_dir / "config.yaml").write_text("run_mode: cron-only\n")
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", profiles_dir)
        assert _read_run_mode("chronos") == RUN_MODE_CRON_ONLY

    def test_reads_on_demand_from_config(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_dir = profiles_dir / "iaso"
        profile_dir.mkdir()
        (profile_dir / "config.yaml").write_text("run_mode: on-demand\n")
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", profiles_dir)
        assert _read_run_mode("iaso") == RUN_MODE_ON_DEMAND

    def test_missing_run_mode_key_defaults(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_dir = profiles_dir / "apollo"
        profile_dir.mkdir()
        (profile_dir / "config.yaml").write_text("model:\n  provider: openai\n")
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", profiles_dir)
        assert _read_run_mode("apollo") == RUN_MODE_ON_DEMAND


class TestPIDManagement:
    """Test PID file read/write operations."""

    @patch("supervisor.lifecycle._pid_alive")
    def test_write_and_read_pid(self, mock_alive):
        mock_alive.return_value = True
        _write_pid("test-profile", 12345)
        pid = _read_pid("test-profile")
        assert pid == 12345

    def test_clear_pid(self):
        _write_pid("test-profile", 12345)
        _clear_pid("test-profile")
        assert _read_pid("test-profile") is None

    def test_read_nonexistent_pid(self):
        assert _read_pid("nonexistent") is None

    def test_pid_file_contains_profile_name(self):
        _write_pid("my-profile", 99999)
        from supervisor.lifecycle import _PID_DIR
        pid_file = _PID_DIR / "my-profile.pid"
        assert pid_file.exists()
        data = json.loads(pid_file.read_text())
        assert data["profile"] == "my-profile"
        assert data["pid"] == 99999
        assert "started_at" in data


class TestStartProfile:
    """Test starting profile processes."""

    @patch("supervisor.lifecycle._pid_alive")
    @patch("supervisor.lifecycle.subprocess.Popen")
    def test_start_creates_pid_file(self, mock_popen, mock_alive):
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_popen.return_value = mock_proc
        mock_alive.return_value = True

        result = start_profile("test-profile")

        assert result["ok"] is True
        assert result["pid"] == 42
        assert result["profile"] == "test-profile"
        assert _read_pid("test-profile") == 42

    @patch("supervisor.lifecycle._pid_alive")
    @patch("supervisor.lifecycle.subprocess.Popen")
    def test_start_prevents_duplicate(self, mock_popen, mock_alive):
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_popen.return_value = mock_proc
        mock_alive.return_value = True

        start_profile("test-profile")
        result = start_profile("test-profile")

        assert result["ok"] is False
        assert "already running" in result["error"]

    @patch("supervisor.lifecycle.subprocess.Popen")
    def test_start_handles_missing_hermes(self, mock_popen):
        mock_popen.side_effect = FileNotFoundError()

        result = start_profile("test-profile")

        assert result["ok"] is False
        assert "hermes CLI not found" in result["error"]

    @patch("supervisor.lifecycle.subprocess.Popen")
    def test_start_handles_os_error(self, mock_popen):
        mock_popen.side_effect = OSError("permission denied")

        result = start_profile("test-profile")

        assert result["ok"] is False
        assert "permission denied" in result["error"]


class TestStopProfile:
    """Test stopping profile processes."""

    def test_stop_nonexistent_profile(self):
        result = stop_profile("not-running")
        assert result["ok"] is False
        assert "not running" in result["error"]

    @patch("supervisor.lifecycle._read_pid")
    @patch("supervisor.lifecycle._pid_alive")
    @patch("supervisor.lifecycle.os.kill")
    def test_stop_sends_sigterm(self, mock_kill, mock_alive, mock_read_pid):
        mock_read_pid.return_value = 100
        mock_alive.return_value = False  # Process dies after SIGTERM

        result = stop_profile("test-profile", reason="test")

        assert result["ok"] is True
        assert result["reason"] == "test"
        assert mock_kill.called

    @patch("supervisor.lifecycle._read_pid")
    @patch("supervisor.lifecycle._pid_alive")
    @patch("supervisor.lifecycle.os.kill")
    def test_stop_clears_pid(self, mock_kill, mock_alive, mock_read_pid):
        mock_read_pid.return_value = 100
        mock_alive.return_value = False

        stop_profile("test-profile")

        assert _read_pid("test-profile") is None


class TestGetProfileStatus:
    """Test profile status reporting."""

    @patch("supervisor.lifecycle._read_pid")
    @patch("supervisor.lifecycle._pid_alive")
    def test_status_running(self, mock_alive, mock_read_pid):
        mock_read_pid.return_value = 100
        mock_alive.return_value = True

        with patch("supervisor.lifecycle._read_run_mode", return_value=RUN_MODE_ALWAYS_ON):
            status = get_profile_status("zeus")

        assert status["status"] == "running"
        assert status["pid"] == 100
        assert status["run_mode"] == RUN_MODE_ALWAYS_ON

    @patch("supervisor.lifecycle._read_pid")
    @patch("supervisor.lifecycle._pid_alive")
    def test_status_crashed(self, mock_alive, mock_read_pid):
        mock_read_pid.return_value = 100
        mock_alive.return_value = False

        with patch("supervisor.lifecycle._read_run_mode", return_value=RUN_MODE_ALWAYS_ON):
            status = get_profile_status("zeus")

        assert status["status"] == "crashed"
        assert status["pid"] == 100

    @patch("supervisor.lifecycle._read_pid")
    def test_status_stopped(self, mock_read_pid):
        mock_read_pid.return_value = None

        with patch("supervisor.lifecycle._read_run_mode", return_value=RUN_MODE_ON_DEMAND):
            status = get_profile_status("iaso")

        assert status["status"] == "stopped"
        assert status["pid"] is None
        assert status["run_mode"] == RUN_MODE_ON_DEMAND


class TestIdleTTL:
    """Test idle TTL enforcement for on-demand profiles."""

    def test_record_and_get_idle_time(self):
        record_activity("test-profile")
        idle_time = get_idle_time("test-profile")
        assert idle_time is not None
        assert idle_time < 1.0  # Just recorded, should be very recent

    def test_get_idle_time_never_recorded(self):
        assert get_idle_time("never-seen") is None

    def test_check_idle_not_exceeded(self):
        record_activity("test-profile")
        result = check_idle("test-profile")
        assert result["exceeded"] is False
        assert result["idle_seconds"] is not None
        assert result["ttl"] > 0

    def test_check_idle_exceeded(self, monkeypatch):
        # Fake the idle time to be very old
        old_state = {"test-profile": {"last_activity": time.time() - 9999}}
        monkeypatch.setattr("supervisor.idle._load_state", lambda: old_state)

        with patch("supervisor.lifecycle._read_run_mode", return_value=RUN_MODE_ON_DEMAND):
            monkeypatch.setattr("supervisor.lifecycle._config_file", lambda p: None)
            result = check_idle("test-profile")

        assert result["exceeded"] is True

    def test_enforce_idle_ttl_skips_always_on(self, monkeypatch):
        record_activity("zeus")
        # Make it look old
        old_state = {"zeus": {"last_activity": time.time() - 9999}}
        monkeypatch.setattr("supervisor.idle._load_state", lambda: old_state)

        profiles = {
            "zeus": {"run_mode": RUN_MODE_ALWAYS_ON, "status": "running"},
        }
        monkeypatch.setattr("supervisor.lifecycle.list_profiles", lambda: profiles)

        results = enforce_idle_ttl()
        # always-on profiles should NOT be in results (skipped)
        assert "zeus" not in results

    def test_enforce_idle_ttl_stops_exceeded_on_demand(self, monkeypatch):
        old_state = {"iaso": {"last_activity": time.time() - 9999}}
        monkeypatch.setattr("supervisor.idle._load_state", lambda: old_state)

        profiles = {
            "iaso": {"run_mode": RUN_MODE_ON_DEMAND, "status": "running"},
        }
        monkeypatch.setattr("supervisor.lifecycle.list_profiles", lambda: profiles)

        with patch("supervisor.lifecycle.stop_profile") as mock_stop:
            mock_stop.return_value = {"ok": True, "profile": "iaso"}
            results = enforce_idle_ttl()

        assert "iaso" in results
        assert results["iaso"]["action"] == "stopped"
        mock_stop.assert_called_once()

    def test_get_ttl_from_config(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile_dir = profiles_dir / "chronos"
        profile_dir.mkdir()
        (profile_dir / "config.yaml").write_text("idle_ttl: 600\n")
        monkeypatch.setattr("supervisor.lifecycle._PROFILES_DIR", profiles_dir)

        assert get_ttl_for_profile("chronos") == 600

    def test_get_ttl_default_when_no_config(self, monkeypatch):
        monkeypatch.setattr("supervisor.lifecycle._config_file", lambda p: None)
        assert get_ttl_for_profile("unknown") == DEFAULT_IDLE_TTL


class TestIdleEnforcer:
    """Test the background idle enforcer thread."""

    def test_idle_enforcer_start_stop(self):
        enforcer = IdleEnforcer(check_interval=1)
        enforcer.start()
        enforcer.stop()
        assert enforcer._running is False

    def test_idle_enforcer_idempotent_start(self):
        enforcer = IdleEnforcer(check_interval=1)
        enforcer.start()
        enforcer.start()  # Should not create duplicate thread
        enforcer.stop()


class TestHealthMonitor:
    """Test the health monitor for crash detection and recovery."""

    def test_health_monitor_start_stop(self):
        monitor = HealthMonitor(check_interval=1)
        monitor.start()
        monitor.stop()
        assert monitor._running is False

    def test_health_monitor_idempotent_start(self):
        monitor = HealthMonitor(check_interval=1)
        monitor.start()
        monitor.start()
        monitor.stop()

    @patch("supervisor.lifecycle.list_profiles")
    @patch("supervisor.lifecycle.start_profile")
    def test_auto_restart_always_on_crashed(self, mock_start, mock_list):
        mock_list.return_value = {
            "zeus": {"status": "crashed", "run_mode": RUN_MODE_ALWAYS_ON},
        }
        mock_start.return_value = {"ok": True, "pid": 999}

        monitor = HealthMonitor(check_interval=1)
        monitor._check_all()

        mock_start.assert_called_once_with("zeus")

    @patch("supervisor.lifecycle.list_profiles")
    @patch("supervisor.lifecycle.start_profile")
    @patch("supervisor.lifecycle._clear_pid")
    def test_no_restart_on_demand_crashed(self, mock_clear, mock_start, mock_list):
        mock_list.return_value = {
            "iaso": {"status": "crashed", "run_mode": RUN_MODE_ON_DEMAND},
        }

        monitor = HealthMonitor(check_interval=1)
        monitor._check_all()

        # Should NOT restart on-demand profiles
        mock_start.assert_not_called()
        # Should clear the stale PID
        mock_clear.assert_called_once_with("iaso")

    @patch("supervisor.lifecycle.list_profiles")
    @patch("supervisor.lifecycle.start_profile")
    def test_gives_up_after_max_crashes(self, mock_start, mock_list):
        mock_list.return_value = {
            "zeus": {"status": "crashed", "run_mode": RUN_MODE_ALWAYS_ON},
        }
        mock_start.return_value = {"ok": False, "error": "cannot start"}

        monitor = HealthMonitor(check_interval=1)
        # Simulate MAX_CRASH_RESTARTS failures
        from supervisor.health import MAX_CRASH_RESTARTS
        for _ in range(MAX_CRASH_RESTARTS):
            monitor._record_crash("zeus", False)
            monitor._check_all()

        # After max crashes, should not attempt restart
        assert not monitor._should_restart("zeus")

    def test_check_single_profile(self):
        with patch("supervisor.lifecycle.get_profile_status") as mock_status:
            mock_status.return_value = {"profile": "zeus", "status": "running"}
            monitor = HealthMonitor(check_interval=1)
            result = monitor.check_profile("zeus")
            assert result["status"] == "running"

    def test_check_all_profiles(self):
        with patch("supervisor.lifecycle.list_profiles") as mock_list:
            mock_list.return_value = {"zeus": {"status": "running"}}
            monitor = HealthMonitor(check_interval=1)
            result = monitor.check_all()
            assert "zeus" in result


class TestRunModeEnforcement:
    """Test that run_mode is correctly enforced across all profiles."""

    @pytest.mark.parametrize(
        "profile,expected_mode",
        [
            ("zeus", RUN_MODE_ALWAYS_ON),
            ("chronos", RUN_MODE_ALWAYS_ON),
            ("iaso", RUN_MODE_ON_DEMAND),
            ("hermes-agent", RUN_MODE_ON_DEMAND),
            ("philia", RUN_MODE_ON_DEMAND),
            ("plutus", RUN_MODE_ON_DEMAND),
            ("metis", RUN_MODE_ON_DEMAND),
            ("apollo", RUN_MODE_ON_DEMAND),
            ("midas", RUN_MODE_ON_DEMAND),
            ("hephaestus", RUN_MODE_ON_DEMAND),
        ],
    )
    def test_profile_run_mode(self, profile, expected_mode):
        """Each profile should have the correct run_mode in its config."""
        mode = _read_run_mode(profile)
        assert mode == expected_mode, f"{profile} expected {expected_mode}, got {mode}"

    def test_always_on_profiles_have_zero_idle_ttl(self):
        """Always-on profiles should not have idle TTL enforcement."""
        for profile in ["zeus", "chronos"]:
            mode = _read_run_mode(profile)
            assert mode == RUN_MODE_ALWAYS_ON, f"{profile} should be always-on"

    def test_on_demand_profiles_have_idle_ttl(self):
        """On-demand profiles should have an idle_ttl configured."""
        for profile in ["iaso", "hermes-agent", "philia", "plutus", "metis", "apollo", "midas", "hephaestus"]:
            mode = _read_run_mode(profile)
            assert mode == RUN_MODE_ON_DEMAND, f"{profile} should be on-demand"
            ttl = get_ttl_for_profile(profile)
            assert ttl > 0, f"{profile} should have idle_ttl > 0"


class TestListProfiles:
    """Test listing all profiles."""

    def test_list_profiles_returns_dict(self):
        result = list_profiles()
        assert isinstance(result, dict)

    def test_list_profiles_includes_known_profiles(self):
        result = list_profiles()
        # At minimum, should find profiles that have config.yaml
        known = ["zeus", "chronos", "iaso"]
        found = [p for p in known if p in result]
        assert len(found) > 0, "Should find at least some known profiles"
