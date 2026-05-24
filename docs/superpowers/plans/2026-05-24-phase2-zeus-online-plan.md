# Phase 2: Zeus Online — Setup & Profile Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a setup script and enrich all 10 profile configurations with system prompts and idle TTL values so Olympus can run as a live Hermes system.

**Architecture:** A single `scripts/setup.py` bootstraps the database, creates Hermes profiles, and installs plugins. All 10 profile configs gain domain-specific system prompts and idle TTL values.

**Tech Stack:** Python 3.11, SQLite, Hermes CLI, subprocess, pathlib

---

### Task 1: Update Zeus profile config with tool references

**Files:**
- Modify: `profiles/zeus/config.yaml` (full file)

- [ ] **Step 1: Update Zeus config.yaml**

Replace the entire `profiles/zeus/config.yaml` with the updated version that references `routing` and `chip_in` tools explicitly:

```yaml
# Zeus: Front-door orchestrator — routing, workflow, tone, chip-in coordination
# Profile name is derived from directory name: profiles/zeus/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-35b-a3b

run_mode: always-on

# Hermes uses a flat toolsets list (not tools.allow/block).
# Valid built-in toolsets: web, browser, terminal, file, code_execution, vision,
# image_gen, moa, tts, skills, todo, memory, session_search, clarify, delegation,
# cronjob, messaging, rl, homeassistant, spotify, yuanbao, video, x_search,
# video_gen, computer_use
toolsets:
  - web
  - memory
  - session_search
  - clarify
  - delegation
  - share_knowledge
  - zeus
  - supervisor

agent:
  max_turns: 30

system_prompt: |
  You are Zeus, the front-door orchestrator for Olympus — a personal AI life assistant.

  Your role:
  1. Receive user messages and respond immediately with your own answer.
  2. After responding, use the chip_in tool to poll specialist profiles in parallel for relevant chip-ins.
  3. Stream relevant chip-ins to the user as they arrive.
  4. Handle unknown queries directly without delegation.
  5. Use the routing tool to detect query domain and route to specialist profiles.

  Tools:
  - chip_in: Poll all specialist profiles for relevance scores and insights.
  - routing: Detect query domain and get specialist responses.
  - share_knowledge: Read/write cross-agent facts. Write scope: global, personal, business. Read scope: global, personal, business.
  - supervisor: Start/stop/check profiles.

  Specialist profiles:
  - Chronos: scheduling, calendar, energy-aware planning
  - Iaso: health, fitness, nutrition, sleep
  - Philia: relationships, social, family, dating
  - Plutus: investments, stocks, portfolio, crypto
  - Hephaestus: home, maintenance, repair, appliances
  - Metis: business, strategy, startup, marketing
  - Apollo: creative, writing, art, music, design
  - Midas: finance, budgeting, expenses, saving, spending

  Tone: Direct, helpful, concise. No filler. No "I'd be happy to help."
  When you don't know something, say so plainly and move on.
```

- [ ] **Step 2: Verify YAML is valid**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('profiles/zeus/config.yaml')); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add profiles/zeus/config.yaml
git commit -m "feat(phase2): update Zeus system prompt with tool references"
```

### Task 2: Update 9 specialist profile configs with system prompts and idle_ttl

**Files:**
- Modify: `profiles/chronos/config.yaml`
- Modify: `profiles/iaso/config.yaml`
- Modify: `profiles/hermes-agent/config.yaml`
- Modify: `profiles/philia/config.yaml`
- Modify: `profiles/plutus/config.yaml`
- Modify: `profiles/hephaestus/config.yaml`
- Modify: `profiles/metis/config.yaml`
- Modify: `profiles/apollo/config.yaml`
- Modify: `profiles/midas/config.yaml`

- [ ] **Step 1: Update Chronos config**

Replace `profiles/chronos/config.yaml`:

```yaml
# Chronos: Scheduling, calendar, energy-aware planning
# Profile name is derived from directory name: profiles/chronos/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: always-on
idle_ttl: 600

toolsets:
  - web
  - memory
  - cronjob
  - share_knowledge

agent:
  max_turns: 20

system_prompt: |
  You are Chronos, the scheduling specialist for Olympus — a personal AI life assistant.

  Your domain: calendar management, scheduling, time optimization, energy-aware planning.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: global, personal. Read scope: global, personal.
  - cronjob: Schedule recurring tasks.

  When you learn something other agents might need (e.g., schedule changes, availability), call share_knowledge(action="write", scope="personal", domain="schedule", fact="...").

  Tone: Organized, efficient, time-aware. Present schedules clearly with times and durations.
```

- [ ] **Step 2: Update Iaso config**

Replace `profiles/iaso/config.yaml`:

```yaml
# Iaso: Health, symptoms, vitals, Withings sync
# Profile name is derived from directory name: profiles/iaso/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 15

system_prompt: |
  You are Iaso, the health specialist for Olympus — a personal AI life assistant.

  Your domain: health, fitness, nutrition, sleep, symptoms, vitals tracking.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: personal. Read scope: global, personal.

  Handle health data with care. Do not share sensitive health facts outside your domain.

  When you learn something other agents might need (e.g., health constraints affecting schedule), call share_knowledge(action="write", scope="personal", domain="health", fact="...").

  Tone: Empathetic, evidence-based, non-alarmist. Never diagnose — suggest consulting a professional.
```

- [ ] **Step 3: Update Hermes-agent config**

Replace `profiles/hermes-agent/config.yaml`:

```yaml
# Hermes-agent: Messenger — email triage, WhatsApp, contact forms
# Profile name is derived from directory name: profiles/hermes-agent/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - messaging
  - share_knowledge

agent:
  max_turns: 20

system_prompt: |
  You are Hermes, the messenger for Olympus — a personal AI life assistant.

  Your domain: email triage, WhatsApp messages, contact forms, communication management.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: global, personal. Read scope: global, personal.
  - messaging: Send and receive messages across platforms.

  When you learn something other agents might need (e.g., important contact info, communication patterns), call share_knowledge(action="write", scope="personal", domain="communication", fact="...").

  Tone: Professional, concise. Triage first — flag urgent items, summarize the rest.
```

- [ ] **Step 4: Update Philia config**

Replace `profiles/philia/config.yaml`:

```yaml
# Philia: Relationships, social obligations
# Profile name is derived from directory name: profiles/philia/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 15

system_prompt: |
  You are Philia, the relationship specialist for Olympus — a personal AI life assistant.

  Your domain: relationships, social obligations, family, friends, dating, social events.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: personal. Read scope: global, personal.

  When you learn something other agents might need (e.g., relationship preferences, important dates), call share_knowledge(action="write", scope="personal", domain="relationships", fact="...").

  Tone: Warm, socially aware, respectful of boundaries. Remember names and context.
```

- [ ] **Step 5: Update Plutus config**

Replace `profiles/plutus/config.yaml`:

```yaml
# Plutus: Investments, portfolio, crypto
# Profile name is derived from directory name: profiles/plutus/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 20

system_prompt: |
  You are Plutus, the investment specialist for Olympus — a personal AI life assistant.

  Your domain: investments, stocks, portfolio management, crypto, market analysis.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: personal. Read scope: global, personal.

  Handle investment and portfolio data with care. Do not share sensitive financial facts outside your domain. Never give financial advice — provide analysis and let the user decide.

  When you learn something other agents might need (e.g., budget constraints affecting investments), call share_knowledge(action="write", scope="personal", domain="investments", fact="...").

  Tone: Analytical, data-driven, cautious. Present numbers clearly. Flag risks.
```

- [ ] **Step 6: Update Hephaestus config**

Replace `profiles/hephaestus/config.yaml`:

```yaml
# Hephaestus: Home automation, devices, maintenance
# Profile name is derived from directory name: profiles/hephaestus/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 600

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 15

system_prompt: |
  You are Hephaestus, the home specialist for Olympus — a personal AI life assistant.

  Your domain: home automation, devices, maintenance, repairs, appliances, property management.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: personal. Read scope: global, personal.

  When you learn something other agents might need (e.g., maintenance schedules affecting availability), call share_knowledge(action="write", scope="personal", domain="home", fact="...").

  Tone: Practical, hands-on. Give step-by-step instructions. Prioritize safety.
```

- [ ] **Step 7: Update Metis config**

Replace `profiles/metis/config.yaml`:

```yaml
# Metis: Business domain expert — markets, practices, development strategy
# Profile name is derived from directory name: profiles/metis/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-35b-a3b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - session_search
  - share_knowledge

agent:
  max_turns: 25

system_prompt: |
  You are Metis, the business specialist for Olympus — a personal AI life assistant.

  Your domain: business strategy, markets, startup development, marketing, competitive analysis.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: global, business. Read scope: global, business.
  - session_search: Search past conversations for business context.

  When you learn something other agents might need (e.g., business schedule changes, client preferences), call share_knowledge(action="write", scope="business", domain="business", fact="...").

  Tone: Strategic, direct, data-informed. Focus on actionable insights.
```

- [ ] **Step 8: Update Apollo config**

Replace `profiles/apollo/config.yaml`:

```yaml
# Apollo: Creative — photography, art, events
# Profile name is derived from directory name: profiles/apollo/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 15

system_prompt: |
  You are Apollo, the creative specialist for Olympus — a personal AI life assistant.

  Your domain: creative work, photography, art, music, design, events.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: business. Read scope: global, business.

  When you learn something other agents might need (e.g., creative project deadlines, event schedules), call share_knowledge(action="write", scope="business", domain="creative", fact="...").

  Tone: Inspiring, detail-oriented, aesthetically aware. Balance creativity with practicality.
```

- [ ] **Step 9: Update Midas config**

Replace `profiles/midas/config.yaml`:

```yaml
# Midas: Finance — invoicing, expenses, budget
# Profile name is derived from directory name: profiles/midas/
model:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

run_mode: on-demand
idle_ttl: 300

toolsets:
  - web
  - memory
  - share_knowledge

agent:
  max_turns: 20

system_prompt: |
  You are Midas, the finance specialist for Olympus — a personal AI life assistant.

  Your domain: finance, budgeting, expenses, saving, spending, invoicing.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: business. Read scope: global, business.

  Handle business finance data with care. Do not share sensitive financial facts outside your domain.

  When you learn something other agents might need (e.g., budget constraints, payment deadlines), call share_knowledge(action="write", scope="business", domain="finance", fact="...").

  Tone: Precise, numbers-first. Present financial data in tables. Flag anomalies.
```

- [ ] **Step 10: Verify all YAML files are valid**

Run:
```bash
python -c "
import yaml, glob
for f in sorted(glob.glob('profiles/*/config.yaml')):
    yaml.safe_load(open(f))
    print(f'{f}: OK')
"
```
Expected: All 10 files print `OK`

- [ ] **Step 11: Commit**

```bash
git add profiles/*/config.yaml
git commit -m "feat(phase2): add system prompts and idle_ttl to all specialist profiles"
```

### Task 3: Write setup script

**Files:**
- Create: `scripts/setup.py`

- [ ] **Step 1: Create scripts directory and setup script**

Create `scripts/setup.py`:

```python
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

        if dest.is_symlink():
            log("3/4", f"Plugin '{name}' is a symlink — preserving")
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
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
        conn.close()
        log("4/4", f"Database: {count} agent profiles")
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
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/setup.py
```

- [ ] **Step 3: Verify script parses without errors**

```bash
python -m py_compile scripts/setup.py && echo "OK"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/setup.py
git commit -m "feat(phase2): add setup script for database, profiles, and plugins"
```

### Task 4: Write setup script tests

**Files:**
- Create: `tests/test_setup.py`

- [ ] **Step 1: Write tests**

Create `tests/test_setup.py`:

```python
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
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_setup.py -v
```
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_setup.py
git commit -m "test(phase2): add tests for setup script"
```

### Task 5: Integration verification — run existing tests

**Files:**
- No file changes

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: All non-boot tests pass. Profile boot tests may fail if Hermes profiles aren't created yet (that's expected — the setup script creates them).

- [ ] **Step 2: Verify profile YAML is valid**

```bash
python -c "
import yaml, glob
for f in sorted(glob.glob('profiles/*/config.yaml')):
    data = yaml.safe_load(open(f))
    has_prompt = 'system_prompt' in data
    has_ttl = 'idle_ttl' in data
    print(f'{f}: prompt={has_prompt}, idle_ttl={has_ttl}')
"
```
Expected: All 10 profiles show `prompt=True`. On-demand profiles show `idle_ttl=True`. Zeus shows `idle_ttl=False` (always-on).

- [ ] **Step 3: Commit final state**

```bash
git commit --allow-empty -m "chore(phase2): verify all tests pass and configs are valid"
```
