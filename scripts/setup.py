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

try:
    import yaml
except ImportError:
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HERMES_HOME = Path.home() / ".hermes"
DB_PATH = HERMES_HOME / "olympus.db"
PLUGINS_DIR = PROJECT_ROOT / "plugins"
PROFILES_DIR = PROJECT_ROOT / "profiles"
SCHEMA_DIR = PROJECT_ROOT / "schema"

EXPECTED_PLUGINS = ["zeus", "supervisor", "revolt", "olympus-dashboard", "share_knowledge", "hephaestus", "iaso"]
EXPECTED_PROFILES = [
    "zeus", "chronos", "iaso", "hermes-agent", "philia",
    "plutus", "hephaestus", "metis", "apollo", "midas",
]

CRON_JOBS = [
    {
        "name": "morning-briefing",
        "schedule": "0 7 * * *",
        "profile": "zeus",
        "prompt": "Generate the morning briefing for the user. Check calendar, health sync, and email triage. Provide consolidated briefing with schedule, urgent items, health status, and energy suggestions.",
    },
    {
        "name": "email-triage",
        "schedule": "every 30m",
        "profile": "hermes-agent",
        "prompt": "Check for new emails and triage them by priority. Summarize urgent items, flag anything requiring immediate attention, and note any messages from important contacts. Store triage summary in share_knowledge with scope=personal, domain=communication.",
    },
    {
        "name": "health-sync",
        "schedule": "0 8,20 * * *",
        "profile": "iaso",
        "prompt": "Sync health data. Check for any new health metrics, medication schedules, or appointment updates. Store findings in share_knowledge with scope=personal, domain=health. Flag any anomalies or upcoming appointments.",
    },
    {
        "name": "portfolio-check",
        "schedule": "30 9 * * 1-5",
        "profile": "plutus",
        "prompt": "Check investment portfolio status. Review market movements, flag any significant changes, and note any actions needed. Store findings in share_knowledge with scope=personal, domain=investments.",
    },
    {
        "name": "invoice-reminder",
        "schedule": "0 10 1 * *",
        "profile": "midas",
        "prompt": "Check for upcoming invoices, bills, and recurring payments due this month. Send a summary of financial obligations and flag any overdue items. Store findings in share_knowledge with scope=personal, domain=finance.",
    },
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
        # executescript() issues an implicit COMMIT before running.
        # Schema creation is atomic via executescript's own transaction.
        conn.executescript(schema_file.read_text())
        log("1/4", f"Schema applied to {DB_PATH}")

        # Install hephaestus home_maintenance schema
        hephaestus_schema = PROJECT_ROOT / "plugins" / "hephaestus" / "schema" / "001_home_maintenance.sql"
        if hephaestus_schema.exists():
            conn.executescript(hephaestus_schema.read_text())
            log("1/4", "Hephaestus home_maintenance schema installed")
        else:
            log("1/4", "WARNING: Hephaestus schema not found, skipping")

        # Install iaso withings_sync schema
        iaso_schema = PROJECT_ROOT / "plugins" / "iaso" / "schema" / "001_withings_sync.sql"
        if iaso_schema.exists():
            conn.executescript(iaso_schema.read_text())
            log("1/4", "Iaso withings_sync schema installed")
        else:
            log("1/4", "WARNING: Iaso schema not found, skipping")

        # Seed agent_profiles table (commits its own transaction)
        _seed_agent_profiles(conn)
        log("1/4", "agent_profiles seeded")
    except Exception:
        conn.rollback()
        raise
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
    log("2/5", "Profile creation")

    # Get existing profiles — parse first column from table output
    try:
        result = subprocess.run(
            ["hermes", "profile", "list"],
            capture_output=True, text=True, check=True,
        )
        existing = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("─") or line.startswith("Profile"):
                continue
            # Extract profile name (first whitespace-separated token)
            # Strip leading ◆ marker if present
            name = line.split()[0].lstrip("◆").lower()
            if name and name != "default":
                existing.add(name)
    except subprocess.CalledProcessError:
        existing = set()

    for name in EXPECTED_PROFILES:
        if name in existing:
            log("2/5", f"Profile '{name}' already exists — skipping")
            continue

        config = PROFILES_DIR / name / "config.yaml"
        if not config.exists():
            log("2/5", f"WARNING: Config not found for '{name}' — skipping")
            continue

        # Try --config flag first
        try:
            subprocess.run(
                ["hermes", "profile", "create", name, "--config", str(config)],
                capture_output=True, text=True, check=True,
            )
            log("2/5", f"Profile '{name}' created (via --config)")
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
            log("2/5", f"Profile '{name}' created (via copy)")
        except subprocess.CalledProcessError as e:
            log("2/5", f"WARNING: Failed to create profile '{name}': {e.stderr.strip()}")
            log("2/5", f"  Manual fallback: hermes profile create {name} --config {config}")


def phase2b_configure_profiles() -> None:
    """Write SOUL.md and set model config for each profile.

    Hermes v0.14.0 does not read system_prompt or model config from config.yaml.
    System prompts go in SOUL.md. Model config must be set via hermes config set.
    """
    log("3/5", "Profile configuration")

    for name in EXPECTED_PROFILES:
        profile_dir = HERMES_HOME / "profiles" / name
        config_file = PROFILES_DIR / name / "config.yaml"

        if not profile_dir.exists():
            log("3/5", f"WARNING: Profile directory not found for '{name}' — skipping")
            continue

        if not config_file.exists():
            log("3/5", f"WARNING: Config not found for '{name}' — skipping")
            continue

        # Read config.yaml
        if yaml is None:
            log("3/5", f"WARNING: PyYAML not installed — skipping config for '{name}'")
            log("3/5", f"  Install with: pip install pyyaml")
            continue

        with open(config_file) as f:
            config = yaml.safe_load(f)

        # Write SOUL.md from system_prompt
        soul_path = profile_dir / "SOUL.md"
        system_prompt = config.get("system_prompt", "").strip()
        if system_prompt:
            if soul_path.exists():
                existing = soul_path.read_text().strip()
                if existing == system_prompt:
                    log("3/5", f"SOUL.md for '{name}' already up-to-date — skipping")
                else:
                    soul_path.write_text(system_prompt + "\n")
                    log("3/5", f"SOUL.md for '{name}' updated")
            else:
                soul_path.write_text(system_prompt + "\n")
                log("3/5", f"SOUL.md for '{name}' created")
        else:
            log("3/5", f"WARNING: No system_prompt in config for '{name}'")

        # Set model config via hermes CLI
        model = config.get("model", {})
        if model:
            _set_profile_model(name, model)
        else:
            log("3/5", f"WARNING: No model config for '{name}'")


def _set_profile_model(name: str, model: dict) -> None:
    """Set model config for a profile via hermes config set."""
    provider = model.get("provider", "")
    base_url = model.get("base_url", "")
    model_name = model.get("model", "")

    if not all([provider, base_url, model_name]):
        log("3/5", f"WARNING: Incomplete model config for '{name}' — skipping")
        return

    # Hermes v0.14.0 uses 'custom' for openai-compatible endpoints
    if provider == "openai-compatible":
        provider = "custom"

    # Map model names to oMLX-compatible names
    model_map = {
        "qwen3.6-8b": "Qwen3.5-4B",
        "qwen3.6-35b-a3b": "Qwen3.6-35B-A3B",
        "qwen3.6-35b-a3b-light": "Qwen3.6-35B-A3B-Light",
    }
    model_name = model_map.get(model_name.lower(), model_name)

    commands = [
        ["hermes", "-p", name, "config", "set", "model.provider", provider],
        ["hermes", "-p", name, "config", "set", "model.base_url", base_url],
        ["hermes", "-p", name, "config", "set", "model.model", model_name],
    ]

    # Only set api_key if it's not the default
    api_key = model.get("api_key")
    if api_key is not None:
        commands.append(["hermes", "-p", name, "config", "set", "model.api_key", api_key])

    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Hermes outputs "✓ Set ..." — just log the key being set
            key = cmd[-2] if len(cmd) > 2 else cmd[-1]
            log("3/5", f"  {name}: {key} set")
        except subprocess.CalledProcessError as e:
            log("3/5", f"WARNING: Failed to set model config for '{name}': {e.stderr.strip()}")


def phase3_plugins() -> None:
    """Install plugins to ~/.hermes/plugins/."""
    log("4/5", "Plugin installation")

    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    dest_dir = HERMES_HOME / "plugins"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for name in EXPECTED_PLUGINS:
        src = PLUGINS_DIR / name
        dest = dest_dir / name

        if not src.exists():
            log("4/5", f"WARNING: Plugin directory not found: {src}")
            continue

        # Skip if already installed (including symlinks)
        if dest.exists() or dest.is_symlink():
            log("4/5", f"Plugin '{name}' already installed — skipping")
            continue

        # Copy plugin
        if src.is_dir():
            shutil.copytree(src, dest)
            log("4/5", f"Plugin '{name}' installed")
        else:
            log("4/5", f"WARNING: {src} is not a directory — skipping")


def phase3b_cron_jobs() -> None:
    """Create cron jobs for Phase 3b automation."""
    log("5/6", "Cron job setup")

    # Check gateway is running
    try:
        result = subprocess.run(
            ["hermes", "gateway", "status"],
            capture_output=True, text=True, check=False,
        )
        if "not running" in result.stdout.lower():
            log("5/6", "WARNING: Gateway not running — installing...")
            subprocess.run(
                ["hermes", "gateway", "install"],
                capture_output=True, text=True, check=True,
            )
            log("5/6", "Gateway installed")
    except FileNotFoundError:
        log("5/6", "WARNING: Could not check gateway status")

    # Get existing jobs
    try:
        result = subprocess.run(
            ["hermes", "-p", "chronos", "cron", "list"],
            capture_output=True, text=True, check=True,
        )
        existing_names = set()
        for line in result.stdout.splitlines():
            for job in CRON_JOBS:
                if job["name"] in line:
                    existing_names.add(job["name"])
    except subprocess.CalledProcessError:
        existing_names = set()

    for job in CRON_JOBS:
        if job["name"] in existing_names:
            log("5/6", f"Cron job '{job['name']}' already exists — skipping")
            continue

        cmd = [
            "hermes", "-p", "chronos", "cron", "create",
            job["schedule"],
            job["prompt"],
            "--name", job["name"],
            "--profile", job["profile"],
            "--deliver", "origin",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            log("5/6", f"Cron job '{job['name']}' created ({job['schedule']}, profile: {job['profile']})")
        except subprocess.CalledProcessError as e:
            log("5/6", f"WARNING: Failed to create cron job '{job['name']}': {e.stderr.strip()}")


def phase4_verification() -> None:
    """Verify installation."""
    log("5/5", "Verification")

    # Check plugins
    try:
        result = subprocess.run(
            ["hermes", "plugins", "list"],
            capture_output=True, text=True, check=True,
        )
        output = result.stdout.lower()
        for name in EXPECTED_PLUGINS:
            if name in output:
                log("5/5", f"Plugin '{name}' — enabled")
            else:
                log("5/5", f"WARNING: Plugin '{name}' not in enabled list")
    except subprocess.CalledProcessError as e:
        log("5/5", f"WARNING: Could not verify plugins: {e.stderr.strip()}")

    # Check profiles
    try:
        result = subprocess.run(
            ["hermes", "profile", "list"],
            capture_output=True, text=True, check=True,
        )
        output = result.stdout.lower()
        for name in EXPECTED_PROFILES:
            if name in output:
                log("5/5", f"Profile '{name}' — exists")
            else:
                log("5/5", f"WARNING: Profile '{name}' not found")
    except subprocess.CalledProcessError as e:
        log("5/5", f"WARNING: Could not verify profiles: {e.stderr.strip()}")

    # Check database
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
            conn.close()
            if count == 10:
                log("5/5", f"Database: {count} agent profiles")
            else:
                log("5/5", f"WARNING: Database has {count} agent profiles (expected 10)")
        except sqlite3.OperationalError:
            log("5/5", "WARNING: agent_profiles table not found in database")
    else:
        log("5/5", "WARNING: Database not found")


def main() -> None:
    """Run all setup phases."""
    print("=" * 50)
    print("Olympus Setup")
    print("=" * 50)

    check_hermes()
    phase1_database()
    phase2_profiles()
    phase2b_configure_profiles()
    phase3_plugins()
    phase3b_cron_jobs()
    phase4_verification()

    print("=" * 50)
    print("Setup complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
