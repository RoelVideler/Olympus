"""Tests for scripts/setup.py.

Tests validate the setup script's logic without requiring a live Hermes installation.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# We test the setup module's internal functions directly
# by importing from scripts.setup
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
