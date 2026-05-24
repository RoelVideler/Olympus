"""Tests for scripts/setup.py.

Tests validate the setup script's logic without requiring a live Hermes installation.
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestSeedAgentProfiles:
    """Test agent_profiles table seeding."""

    def test_seeds_all_10_profiles(self):
        """All 10 profiles are inserted into agent_profiles."""
        from setup import _seed_agent_profiles

        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE agent_profiles (
                name TEXT PRIMARY KEY,
                hermes_profile TEXT NOT NULL,
                run_mode TEXT NOT NULL,
                model_provider TEXT,
                model_name TEXT,
                status TEXT DEFAULT 'stopped'
            )
        """)

        _seed_agent_profiles(conn)

        count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
        assert count == 10

    def test_seeds_correct_run_modes(self):
        """Always-on profiles have correct run_mode."""
        from setup import _seed_agent_profiles

        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE agent_profiles (
                name TEXT PRIMARY KEY,
                hermes_profile TEXT NOT NULL,
                run_mode TEXT NOT NULL,
                model_provider TEXT,
                model_name TEXT,
                status TEXT DEFAULT 'stopped'
            )
        """)

        _seed_agent_profiles(conn)

        always_on = conn.execute(
            "SELECT name FROM agent_profiles WHERE run_mode = 'always-on'"
        ).fetchall()
        always_on_names = [r[0] for r in always_on]
        assert "zeus" in always_on_names
        assert "chronos" in always_on_names
        assert len(always_on_names) == 2

    def test_idempotent_replacement(self):
        """Running seed twice replaces existing rows (no duplicates)."""
        from setup import _seed_agent_profiles

        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE agent_profiles (
                name TEXT PRIMARY KEY,
                hermes_profile TEXT NOT NULL,
                run_mode TEXT NOT NULL,
                model_provider TEXT,
                model_name TEXT,
                status TEXT DEFAULT 'stopped'
            )
        """)

        _seed_agent_profiles(conn)
        _seed_agent_profiles(conn)  # Run again

        count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
        assert count == 10


class TestSetupScriptStructure:
    """Test that setup script has required components."""

    def test_expected_plugins_list(self):
        """EXPECTED_PLUGINS contains all 5 plugins."""
        from setup import EXPECTED_PLUGINS
        assert len(EXPECTED_PLUGINS) == 5
        assert "zeus" in EXPECTED_PLUGINS
        assert "share_knowledge" in EXPECTED_PLUGINS
        assert "olympus-dashboard" in EXPECTED_PLUGINS

    def test_expected_profiles_list(self):
        """EXPECTED_PROFILES contains all 10 profiles."""
        from setup import EXPECTED_PROFILES
        assert len(EXPECTED_PROFILES) == 10
        assert "zeus" in EXPECTED_PROFILES
        assert "midas" in EXPECTED_PROFILES

    def test_plugin_directories_exist(self):
        """All expected plugin directories exist in the repo."""
        from setup import PLUGINS_DIR, EXPECTED_PLUGINS
        for name in EXPECTED_PLUGINS:
            assert (PLUGINS_DIR / name).exists(), f"Plugin directory missing: {name}"

    def test_profile_configs_exist(self):
        """All expected profile config files exist in the repo."""
        from setup import PROFILES_DIR, EXPECTED_PROFILES
        for name in EXPECTED_PROFILES:
            config = PROFILES_DIR / name / "config.yaml"
            assert config.exists(), f"Profile config missing: {config}"


class TestPhase2Profiles:
    """Test profile creation with mocked subprocess calls."""

    def _make_profile_list_result(self, names):
        """Create a mock result for hermes profile list."""
        result = MagicMock()
        result.stdout = "\n".join(names) + "\n"
        result.returncode = 0
        return result

    def test_skips_existing_profiles(self):
        """Profiles that already exist are skipped."""
        from setup import phase2_profiles, EXPECTED_PROFILES

        all_exist = self._make_profile_list_result(EXPECTED_PROFILES)

        with patch("setup.subprocess.run", return_value=all_exist) as mock_run:
            phase2_profiles()

        # Only hermes profile list should be called, no create calls
        assert mock_run.call_count == 1
        assert "list" in str(mock_run.call_args_list[0])

    def test_creates_missing_profiles(self):
        """Missing profiles are created via --config flag."""
        from setup import phase2_profiles

        # Only zeus exists
        list_result = self._make_profile_list_result(["zeus"])
        create_result = MagicMock()
        create_result.returncode = 0

        # First call is list, then 9 create calls
        call_sequence = [list_result] + [create_result] * 9

        with patch("setup.subprocess.run", side_effect=call_sequence) as mock_run:
            phase2_profiles()

        # Should have called list once, then create 9 times
        assert mock_run.call_count == 10

    def test_fallback_on_config_flag_failure(self):
        """Falls back to copy+create when --config flag fails."""
        from setup import phase2_profiles

        list_result = self._make_profile_list_result([])

        def side_effect(*args, **kwargs):
            """Return list result, then fail all --config calls, succeed all fallback creates."""
            if not hasattr(side_effect, "call_num"):
                side_effect.call_num = 0
            side_effect.call_num += 1

            if side_effect.call_num == 1:
                return list_result
            # Odd calls (2, 4, 6...) are --config attempts - fail
            if side_effect.call_num % 2 == 0:
                raise subprocess.CalledProcessError(1, args[0])
            # Even calls (3, 5, 7...) are fallback creates - succeed
            result = MagicMock()
            result.returncode = 0
            return result

        with patch("setup.subprocess.run", side_effect=side_effect) as mock_run:
            with patch("setup.shutil.copy2"):
                with patch.object(Path, "mkdir", return_value=None):
                    phase2_profiles()

        # 1 list + 10 config fails + 10 fallback creates = 21 calls
        assert mock_run.call_count == 21


class TestPhase3Plugins:
    """Test plugin installation with mocked file operations."""

    def test_skips_existing_plugins(self):
        """Plugins that already exist are skipped."""
        from setup import phase3_plugins

        with patch("setup.Path.exists", return_value=True):
            with patch("setup.Path.is_symlink", return_value=False):
                with patch("setup.Path.mkdir"):
                    with patch("setup.shutil.copytree") as mock_copy:
                        phase3_plugins()
                        assert mock_copy.call_count == 0


class TestPhase4Verification:
    """Test verification with mocked subprocess calls."""

    def test_reports_enabled_plugins(self):
        """Verification reports enabled plugins correctly."""
        from setup import phase4_verification

        plugins_result = MagicMock()
        plugins_result.stdout = "zeus\nsupervisor\nrevolt\nolympus-dashboard\nshare_knowledge\n"
        plugins_result.returncode = 0

        profiles_result = MagicMock()
        profiles_result.stdout = "zeus\nchronos\niaso\nhermes-agent\nphilia\nplutus\nhephaestus\nmetis\napollo\nmidas\n"
        profiles_result.returncode = 0

        with patch("setup.subprocess.run", side_effect=[plugins_result, profiles_result]):
            with patch("setup.Path.exists", return_value=True):
                with patch("setup.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.execute.return_value.fetchone.return_value = [10]
                    mock_connect.return_value = mock_conn
                    phase4_verification()

    def test_warns_on_missing_database(self):
        """Verification warns when database doesn't exist."""
        from setup import phase4_verification

        plugins_result = MagicMock()
        plugins_result.stdout = ""
        plugins_result.returncode = 0

        profiles_result = MagicMock()
        profiles_result.stdout = ""
        profiles_result.returncode = 0

        with patch("setup.subprocess.run", side_effect=[plugins_result, profiles_result]):
            with patch("setup.Path.exists", return_value=False):
                phase4_verification()  # Should not raise
