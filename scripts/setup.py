#!/usr/bin/env python3
"""Olympus setup script — bootstrap database, profiles, and plugins.

Usage:
    python scripts/setup.py

This script is idempotent — safe to run multiple times.
Requires Hermes CLI to be installed. Does NOT require Ollama or LLM provider.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HERMES_HOME = Path.home() / ".hermes"
DB_PATH = HERMES_HOME / "olympus.db"
PLUGINS_DIR = PROJECT_ROOT / "plugins"
PROFILES_DIR = PROJECT_ROOT / "profiles"
SCHEMA_DIR = PROJECT_ROOT / "schema"

EXPECTED_PLUGINS = ["zeus", "supervisor", "revolt", "olympus-dashboard", "share_knowledge"]
EXPECTED_PROFILES = [
    "zeus", "chronos", "iaso", "hermes-agent", "philia",
    "plutus", "hephaestus", "metis", "apollo", "midas",
]


def log(phase: str, msg: str) -> None:
    print(f"[{phase}] {msg}")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_hermes() -> None:
    """Verify Hermes CLI is installed."""
    try:
        result = subprocess.run(
            ["hermes", "--version"],
            capture_output=True, text=True, check=True,
        )
        version = result.stdout.strip()
        log("check", f"Hermes found: {version}")
    except FileNotFoundError:
        fail("Hermes CLI not found. Install with: pip install hermes-agent")
    except subprocess.CalledProcessError as e:
        fail(f"Hermes CLI error: {e.stderr.strip()}")


def phase1_database() -> None:
    """Initialize SQLite database from schema."""
    log("1/4", "Database init")

    HERMES_HOME.mkdir(parents=True, exist_ok=True)

    schema_file = SCHEMA_DIR / "001_initial.sql"
    if not schema_file.exists():
        fail(f"Schema file not found: {schema_file}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(schema_file.read_text())
        log("1/4", f"Schema applied to {DB_PATH}")

        # Seed agent_profiles table
        _seed_agent_profiles(conn)
        log("1/4", "agent_profiles seeded")
    finally:
        conn.close()


def _seed_agent_profiles(conn: sqlite3.Connection) -> None:
    """Populate agent_profiles table with all 10 profiles."""
    profiles = [
        ("zeus", "zeus", "always-on", "openai-compatible", "qwen3.6-35b-a3b"),
        ("chronos", "chronos", "always-on", "openai-compatible", "qwen3.6-8b"),
        ("iaso", "iaso", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("hermes-agent", "hermes-agent", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("philia", "philia", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("plutus", "plutus", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("hephaestus", "hephaestus", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("metis", "metis", "on-demand", "openai-compatible", "qwen3.6-35b-a3b"),
        ("apollo", "apollo", "on-demand", "openai-compatible", "qwen3.6-8b"),
        ("midas", "midas", "on-demand", "openai-compatible", "qwen3.6-8b"),
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO agent_profiles
           (name, hermes_profile, run_mode, model_provider, model_name, status)
           VALUES (?, ?, ?, ?, ?, 'stopped')""",
        profiles,
    )
    conn.commit()


def phase2_profiles() -> None:
    """Create Hermes profiles from config files."""
    log("2/4", "Profile creation")

    # Get existing profiles
    try:
        result = subprocess.run(
            ["hermes", "profile", "list"],
            capture_output=True, text=True, check=True,
        )
        existing = result.stdout.lower()
    except subprocess.CalledProcessError:
        existing = ""

    for name in EXPECTED_PROFILES:
        if name in existing:
            log("2/4", f"Profile '{name}' already exists — skipping")
            continue

        config = PROFILES_DIR / name / "config.yaml"
        if not config.exists():
            log("2/4", f"WARNING: Config not found for '{name}' — skipping")
            continue

        # Try --config flag first
        try:
            subprocess.run(
                ["hermes", "profile", "create", name, "--config", str(config)],
                capture_output=True, text=True, check=True,
            )
            log("2/4", f"Profile '{name}' created (via --config)")
            continue
        except subprocess.CalledProcessError:
            pass

        # Fallback: copy config then create
        dest = HERMES_HOME / name / "config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config, dest)
        try:
            subprocess.run(
                ["hermes", "profile", "create", name],
                capture_output=True, text=True, check=True,
            )
            log("2/4", f"Profile '{name}' created (via copy)")
        except subprocess.CalledProcessError as e:
            log("2/4", f"WARNING: Failed to create profile '{name}': {e.stderr.strip()}")
            log("2/4", f"  Manual fallback: hermes profile create {name} --config {config}")


def phase3_plugins() -> None:
    """Install plugins to ~/.hermes/plugins/."""
    log("3/4", "Plugin installation")

    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    dest_dir = HERMES_HOME / "plugins"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for name in EXPECTED_PLUGINS:
        src = PLUGINS_DIR / name
        dest = dest_dir / name

        if not src.exists():
            log("3/4", f"WARNING: Plugin directory not found: {src}")
            continue

        # Skip if already installed (including symlinks)
        if dest.exists() or dest.is_symlink():
            log("3/4", f"Plugin '{name}' already installed — skipping")
            continue

        # Copy plugin
        if src.is_dir():
            shutil.copytree(src, dest)
            log("3/4", f"Plugin '{name}' installed")
        else:
            log("3/4", f"WARNING: {src} is not a directory — skipping")


def phase4_verification() -> None:
    """Verify installation."""
    log("4/4", "Verification")

    # Check plugins
    try:
        result = subprocess.run(
            ["hermes", "plugins", "list"],
            capture_output=True, text=True, check=True,
        )
        output = result.stdout.lower()
        for name in EXPECTED_PLUGINS:
            if name in output:
                log("4/4", f"Plugin '{name}' — enabled")
            else:
                log("4/4", f"WARNING: Plugin '{name}' not in enabled list")
    except subprocess.CalledProcessError as e:
        log("4/4", f"WARNING: Could not verify plugins: {e.stderr.strip()}")

    # Check profiles
    try:
        result = subprocess.run(
            ["hermes", "profile", "list"],
            capture_output=True, text=True, check=True,
        )
        output = result.stdout.lower()
        for name in EXPECTED_PROFILES:
            if name in output:
                log("4/4", f"Profile '{name}' — exists")
            else:
                log("4/4", f"WARNING: Profile '{name}' not found")
    except subprocess.CalledProcessError as e:
        log("4/4", f"WARNING: Could not verify profiles: {e.stderr.strip()}")

    # Check database
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
            conn.close()
            if count == 10:
                log("4/4", f"Database: {count} agent profiles")
            else:
                log("4/4", f"WARNING: Database has {count} agent profiles (expected 10)")
        except sqlite3.OperationalError:
            log("4/4", "WARNING: agent_profiles table not found in database")
    else:
        log("4/4", "WARNING: Database not found")


def main() -> None:
    """Run all setup phases."""
    print("=" * 50)
    print("Olympus Setup")
    print("=" * 50)

    check_hermes()
    phase1_database()
    phase2_profiles()
    phase3_plugins()
    phase4_verification()

    print("=" * 50)
    print("Setup complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
