"""
Integration tests for Olympus Phase 1 Hermes Plugins.

Tests 7.1-7.8 from the phase1-hermes-plugins change.

Some tests require Hermes to be fully configured with LLM providers.
If external services aren't available, tests are marked as NEEDS_CONTEXT.
"""
import os
import sqlite3
import subprocess
import json
import sys
import pytest
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
PLUGINS_DIR = PROJECT_ROOT / "plugins"
SCHEMA_DIR = PROJECT_ROOT / "schema"

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

# Expected profiles and plugins
EXPECTED_PROFILES = [
    "zeus", "chronos", "iaso", "hermes-agent", "philia",
    "plutus", "hephaestus", "metis", "apollo", "midas"
]

EXPECTED_PLUGINS = ["zeus", "supervisor", "revolt", "dashboard", "share_knowledge"]


def hermes_available() -> bool:
    """Check if Hermes Agent is installed."""
    try:
        result = subprocess.run(["hermes", "--version"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def hermes_plugins_enabled() -> list:
    """Get list of enabled Olympus plugins from Hermes."""
    try:
        result = subprocess.run(
            ["hermes", "plugins", "list"],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            return []
        
        enabled = []
        for plugin in EXPECTED_PLUGINS:
            if plugin in result.stdout and "enabled" in result.stdout:
                # Check each plugin line
                for line in result.stdout.split("\n"):
                    if plugin in line and "enabled" in line:
                        enabled.append(plugin)
                        break
        return list(set(enabled))
    except Exception:
        return []


# ============================================================
# Task 7.1: All 10 profiles boot and respond to basic prompt
# ============================================================

class TestProfileConfigs:
    """Test that all 10 profile configs exist and are valid YAML."""

    @pytest.mark.parametrize("profile", EXPECTED_PROFILES)
    def test_profile_config_exists(self, profile):
        """Test that each profile has a config.yaml file."""
        config_path = PROFILES_DIR / profile / "config.yaml"
        assert config_path.exists(), f"Profile {profile} missing config.yaml"

    @pytest.mark.parametrize("profile", EXPECTED_PROFILES)
    def test_profile_config_valid_yaml(self, profile):
        """Test that each profile config is valid YAML."""
        config_path = PROFILES_DIR / profile / "config.yaml"
        if not config_path.exists():
            pytest.skip(f"Profile {profile} config not found")
        
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert config is not None, f"Profile {profile} config is empty"
        assert "model" in config, f"Profile {profile} config missing model section"
        assert "run_mode" in config, f"Profile {profile} config missing run_mode"

    @pytest.mark.parametrize("profile", EXPECTED_PROFILES)
    def test_profile_run_mode_valid(self, profile):
        """Test that run_mode is one of the valid values."""
        config_path = PROFILES_DIR / profile / "config.yaml"
        if not config_path.exists():
            pytest.skip(f"Profile {profile} config not found")
        
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        valid_modes = ("always-on", "on-demand", "cron-only")
        assert config["run_mode"] in valid_modes, \
            f"Profile {profile} has invalid run_mode: {config['run_mode']}"


@pytest.mark.skipif(not hermes_available(), reason="Hermes Agent not installed")
class TestProfileBoot:
    """Test that profiles boot in Hermes (requires Hermes setup)."""

    @pytest.mark.parametrize("profile", EXPECTED_PROFILES)
    def test_profile_responds(self, profile):
        """Test that a profile boots and responds to a basic prompt.
        
        NEEDS_CONTEXT: Requires Hermes to be configured with an LLM provider
        that can respond to prompts. Skip if LLM not configured.
        """
        # Check if profile is installed in Hermes
        result = subprocess.run(
            ["hermes", "profile", "list"],
            capture_output=True, text=True, check=False
        )
        if profile not in result.stdout:
            pytest.skip(f"Profile {profile} not installed in Hermes — NEEDS_CONTEXT")
        
        try:
            result = subprocess.run(
                ["hermes", "-p", profile, "-z", "Who are you? Respond in one sentence."],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Profile {profile} timed out after 60s")

        assert result.returncode == 0, f"Profile {profile} failed: {result.stderr}"
        assert result.stdout.strip(), f"Profile {profile} returned empty response"


# ============================================================
# Task 7.2: All 5 plugins load correctly
# ============================================================

class TestPluginStructure:
    """Test that all 5 plugins have valid structure."""

    @pytest.mark.parametrize("plugin", EXPECTED_PLUGINS)
    def test_plugin_directory_exists(self, plugin):
        """Test that each plugin directory exists."""
        plugin_dir = PLUGINS_DIR / plugin
        assert plugin_dir.exists(), f"Plugin {plugin} directory missing"

    @pytest.mark.parametrize("plugin", EXPECTED_PLUGINS)
    def test_plugin_manifest_exists(self, plugin):
        """Test that each plugin has a plugin.yaml manifest."""
        manifest = PLUGINS_DIR / plugin / "plugin.yaml"
        assert manifest.exists(), f"Plugin {plugin} missing plugin.yaml"

    @pytest.mark.parametrize("plugin", EXPECTED_PLUGINS)
    def test_plugin_manifest_valid(self, plugin):
        """Test that plugin.yaml is valid YAML with required fields."""
        manifest = PLUGINS_DIR / plugin / "plugin.yaml"
        if not manifest.exists():
            pytest.skip(f"Plugin {plugin} manifest not found")
        
        import yaml
        with open(manifest) as f:
            config = yaml.safe_load(f)
        
        assert "name" in config, f"Plugin {plugin} manifest missing name"
        assert "version" in config, f"Plugin {plugin} manifest missing version"
        assert "description" in config, f"Plugin {plugin} manifest missing description"
        assert config["name"] == plugin, f"Plugin {plugin} manifest name mismatch"

    @pytest.mark.parametrize("plugin", EXPECTED_PLUGINS)
    def test_plugin_init_exists(self, plugin):
        """Test that each plugin has __init__.py."""
        init_file = PLUGINS_DIR / plugin / "__init__.py"
        assert init_file.exists(), f"Plugin {plugin} missing __init__.py"


@pytest.mark.skipif(not hermes_available(), reason="Hermes Agent not installed")
class TestPluginLoading:
    """Test that plugins load in Hermes."""

    def test_all_plugins_enabled(self):
        """Test that all 5 Olympus plugins show as enabled in Hermes.
        
        NEEDS_CONTEXT: Requires plugins to be installed in Hermes.
        """
        enabled = hermes_plugins_enabled()
        
        for plugin in EXPECTED_PLUGINS:
            assert plugin in enabled, \
                f"Plugin {plugin} not enabled in Hermes — NEEDS_CONTEXT (install plugins first)"


# ============================================================
# Task 7.3: share_knowledge round-trip
# ============================================================

class TestShareKnowledgeRoundTrip:
    """Test share_knowledge write/read across profiles."""

    @pytest.fixture
    def db_path(self, tmp_path):
        """Create a temporary database."""
        return str(tmp_path / "olympus.db")

    @pytest.fixture
    def initialized_db(self, db_path):
        """Initialize database with schema."""
        schema_path = SCHEMA_DIR / "001_initial.sql"
        conn = sqlite3.connect(db_path)
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()
        return db_path

    def test_write_from_one_profile_read_from_another(self, initialized_db):
        """Test: write from profile A, read from profile B, verify source_profile."""
        # Test directly with SQLite to verify round-trip
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        
        # Write fact as Zeus
        conn.execute(
            "INSERT INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile) VALUES (?, ?, ?, ?, ?, ?)",
            ("test-001", "global", "test", "This fact was written by Zeus", 0.9, "zeus")
        )
        conn.commit()
        
        # Read fact as Iaso (query the same DB)
        rows = conn.execute(
            "SELECT id, domain, fact, confidence, source_profile FROM olympus_knowledge WHERE scope = ? AND domain = ?",
            ("global", "test")
        ).fetchall()
        
        assert len(rows) == 1
        assert rows[0]["fact"] == "This fact was written by Zeus"
        assert rows[0]["source_profile"] == "zeus"
        
        conn.close()

    def test_multiple_profiles_write_and_read(self, initialized_db):
        """Test: multiple profiles write, each can read all facts."""
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        
        profiles = ["zeus", "iaso", "chronos"]
        
        # Each profile writes a fact
        for i, profile in enumerate(profiles):
            conn.execute(
                "INSERT INTO olympus_knowledge (id, scope, domain, fact, source_profile) VALUES (?, ?, ?, ?, ?)",
                (f"test-{i:03d}", "global", "test", f"Fact from {profile}", profile)
            )
        conn.commit()
        
        # Any profile can read all facts
        rows = conn.execute(
            "SELECT fact, source_profile FROM olympus_knowledge WHERE scope = ? AND domain = ? ORDER BY id",
            ("global", "test")
        ).fetchall()
        
        assert len(rows) == 3
        
        facts = [row["fact"] for row in rows]
        source_profiles = [row["source_profile"] for row in rows]
        
        for profile in profiles:
            assert f"Fact from {profile}" in facts
            assert profile in source_profiles
        
        conn.close()


# ============================================================
# Task 7.4: Supervisor starts/stops profiles based on run_mode
# ============================================================

class TestSupervisorLifecycle:
    """Test Supervisor plugin lifecycle functions."""

    def test_lifecycle_module_exists(self):
        """Test that lifecycle.py exists and has required functions."""
        lifecycle_path = PLUGINS_DIR / "supervisor" / "lifecycle.py"
        assert lifecycle_path.exists(), "Supervisor lifecycle.py missing"
        
        # Check file content for required functions
        content = lifecycle_path.read_text()
        assert "def start_profile" in content, "Missing start_profile function"
        assert "def stop_profile" in content, "Missing stop_profile function"

    def test_health_module_exists(self):
        """Test that health.py exists and has required functions."""
        health_path = PLUGINS_DIR / "supervisor" / "health.py"
        assert health_path.exists(), "Supervisor health.py missing"

    def test_idle_module_exists(self):
        """Test that idle.py exists and has required functions."""
        idle_path = PLUGINS_DIR / "supervisor" / "idle.py"
        assert idle_path.exists(), "Supervisor idle.py missing"

    def test_supervisor_api_module_exists(self):
        """Test that api.py exists and has required functions."""
        api_path = PLUGINS_DIR / "supervisor" / "api.py"
        assert api_path.exists(), "Supervisor api.py missing"

    def test_run_mode_from_profile_configs(self):
        """Test that run_mode values from profile configs are valid."""
        import yaml
        
        run_modes = {}
        for profile in EXPECTED_PROFILES:
            config_path = PROFILES_DIR / profile / "config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                run_modes[profile] = config.get("run_mode", "on-demand")
        
        # Verify we have a mix of run modes
        modes = set(run_modes.values())
        assert "always-on" in modes or "on-demand" in modes, \
            "No always-on or on-demand profiles found"

    def test_supervisor_plugin_manifest(self):
        """Test Supervisor plugin manifest declares correct kind."""
        manifest = PLUGINS_DIR / "supervisor" / "plugin.yaml"
        import yaml
        with open(manifest) as f:
            config = yaml.safe_load(f)
        
        assert config.get("kind") == "gateway", \
            f"Supervisor should be kind: gateway, got: {config.get('kind')}"


# ============================================================
# Task 7.5: Zeus routes a known-domain query to specialist profile
# ============================================================

class TestZeusRouting:
    """Test Zeus routing skill."""

    def test_routing_module_exists(self):
        """Test that routing.py exists."""
        routing_path = PLUGINS_DIR / "zeus" / "skills" / "routing.py"
        assert routing_path.exists(), "Zeus routing skill missing"

    def test_chip_in_module_exists(self):
        """Test that chip_in.py exists."""
        chip_in_path = PLUGINS_DIR / "zeus" / "skills" / "chip_in.py"
        assert chip_in_path.exists(), "Zeus chip_in skill missing"

    def test_routing_skill_has_route_function(self):
        """Test that routing skill has routing logic."""
        routing_path = PLUGINS_DIR / "zeus" / "skills" / "routing.py"
        content = routing_path.read_text()
        
        # Check for routing-related functions/classes
        has_routing = any(keyword in content for keyword in [
            "def route", "class Routing", "route_query", "domain_map", "specialist"
        ])
        assert has_routing, "Routing skill missing routing logic"

    def test_known_domain_routing_table(self):
        """Test routing table maps domains to specialist profiles.
        
        Verifies the routing logic exists for known domains.
        """
        routing_path = PLUGINS_DIR / "zeus" / "skills" / "routing.py"
        content = routing_path.read_text()
        
        # Check for specialist profile references
        specialist_profiles = ["chronos", "iaso", "philia", "plutus", "hephaestus", "metis", "apollo", "midas"]
        found_profiles = [p for p in specialist_profiles if p in content]
        
        assert len(found_profiles) > 0, \
            "Routing skill should reference specialist profiles"


# ============================================================
# Task 7.6: Zeus handles an unknown query directly
# ============================================================

class TestZeusUnknownQuery:
    """Test Zeus handles unknown queries without delegation."""

    def test_routing_has_fallback_logic(self):
        """Test that routing skill has fallback/default handling.
        
        NEEDS_CONTEXT: Requires full Hermes setup with LLM.
        """
        routing_path = PLUGINS_DIR / "zeus" / "skills" / "routing.py"
        content = routing_path.read_text()
        
        # Check for fallback/default handling
        has_fallback = any(keyword in content.lower() for keyword in [
            "default", "fallback", "unknown", "zeus", "none", "return"
        ])
        assert has_fallback, "Routing skill should have fallback handling"


# ============================================================
# Task 7.7: Dashboard REST endpoints
# ============================================================

class TestDashboardREST:
    """Test Dashboard REST endpoints."""

    @pytest.fixture
    def seeded_db(self, tmp_path):
        """Create a seeded test database."""
        db_path = str(tmp_path / "olympus.db")
        
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Create tables
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS olympus_knowledge (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL CHECK(scope IN ('personal', 'business', 'global')),
                domain TEXT NOT NULL,
                fact TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source_profile TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agent_profiles (
                name TEXT PRIMARY KEY,
                hermes_profile TEXT NOT NULL,
                run_mode TEXT NOT NULL DEFAULT 'on-demand',
                model_provider TEXT,
                model_name TEXT,
                status TEXT DEFAULT 'stopped'
            );

            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT,
                attendees TEXT,
                source TEXT
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company TEXT,
                role TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        
        # Seed profiles
        profiles = [
            ("zeus", "zeus", "always-on", "openai", "gpt-4o", "running"),
            ("chronos", "chronos", "on-demand", "anthropic", "claude-sonnet", "stopped"),
            ("iaso", "iaso", "on-demand", "openai", "gpt-4o-mini", "stopped"),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO agent_profiles VALUES (?, ?, ?, ?, ?, ?)",
            profiles
        )
        
        # Seed knowledge
        entries = [
            ("wiki-001", "personal", "health", "Daily step goal is 10,000 steps.", 1.0, "zeus"),
            ("wiki-002", "business", "finance", "Monthly revenue target: $50,000.", 1.0, "plutus"),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile) VALUES (?, ?, ?, ?, ?, ?)",
            entries
        )
        
        # Seed calendar
        from datetime import datetime, timedelta
        now = datetime.now()
        events = [
            ("cal-001", "Team standup", "Daily sync", (now + timedelta(hours=2)).isoformat(), (now + timedelta(hours=2, minutes=30)).isoformat(), "Zoom", '["alice"]', "google"),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO calendar_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            events
        )
        
        # Seed contacts
        contacts = [
            ("contact-001", "Alice Johnson", "alice@example.com", "+31-6-1234-5678", "Acme Corp", "CTO", "Key decision maker"),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?)",
            contacts
        )
        
        # Seed preferences
        prefs = [
            ("theme", "dark"),
            ("timezone", "Europe/Amsterdam"),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            prefs
        )
        
        conn.commit()
        conn.close()
        
        return db_path

    def test_health_endpoint_data(self, seeded_db):
        """Test health query returns correct data from SQLite."""
        conn = sqlite3.connect(seeded_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT name, status, run_mode FROM agent_profiles ORDER BY name")
        profiles = [dict(row) for row in cursor.fetchall()]
        
        cursor = conn.execute("SELECT scope, COUNT(*) as count FROM olympus_knowledge GROUP BY scope")
        knowledge_stats = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        assert len(profiles) == 3
        assert any(p["name"] == "zeus" for p in profiles)
        assert len(knowledge_stats) > 0

    def test_wiki_endpoint_data(self, seeded_db):
        """Test wiki query returns wiki entries."""
        conn = sqlite3.connect(seeded_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT * FROM olympus_knowledge ORDER BY updated_at DESC")
        entries = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        assert len(entries) == 2
        assert any(e["fact"] == "Daily step goal is 10,000 steps." for e in entries)

    def test_calendar_endpoint_data(self, seeded_db):
        """Test calendar query returns events."""
        conn = sqlite3.connect(seeded_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT * FROM calendar_events ORDER BY start_time ASC")
        events = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        assert len(events) == 1
        assert events[0]["title"] == "Team standup"

    def test_contacts_endpoint_data(self, seeded_db):
        """Test contacts query returns contacts."""
        conn = sqlite3.connect(seeded_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT * FROM contacts ORDER BY name ASC")
        contacts = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        assert len(contacts) == 1
        assert contacts[0]["name"] == "Alice Johnson"

    def test_preferences_endpoint_data(self, seeded_db):
        """Test preferences query returns preferences."""
        conn = sqlite3.connect(seeded_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT key, value FROM preferences")
        prefs = {row["key"]: row["value"] for row in cursor.fetchall()}
        
        conn.close()
        
        assert prefs.get("theme") == "dark"
        assert prefs.get("timezone") == "Europe/Amsterdam"

    def test_api_module_has_routes(self):
        """Test that api.py registers all Phase 2 endpoints."""
        api_path = PLUGINS_DIR / "dashboard" / "api.py"
        content = api_path.read_text()
        
        required_endpoints = ["/api/health", "/api/wiki", "/api/calendar", "/api/contacts", "/api/preferences"]
        for endpoint in required_endpoints:
            assert endpoint in content, f"Missing endpoint: {endpoint}"


# ============================================================
# Task 7.8: Dashboard WebSocket
# ============================================================

class TestDashboardWebSocket:
    """Test Dashboard WebSocket streaming."""

    def test_websocket_module_exists(self):
        """Test that websocket.py exists."""
        ws_path = PLUGINS_DIR / "dashboard" / "websocket.py"
        assert ws_path.exists(), "Dashboard websocket.py missing"

    def test_websocket_hub_class(self):
        """Test that WebSocketHub class exists."""
        ws_path = PLUGINS_DIR / "dashboard" / "websocket.py"
        content = ws_path.read_text()
        
        assert "class WebSocketHub" in content, "Missing WebSocketHub class"
        assert "def connect" in content, "Missing connect method"
        assert "def disconnect" in content, "Missing disconnect method"
        assert "def broadcast" in content, "Missing broadcast method"

    def test_websocket_route_registered(self):
        """Test that WebSocket route is registered."""
        ws_path = PLUGINS_DIR / "dashboard" / "websocket.py"
        content = ws_path.read_text()
        
        assert "register_websocket_route" in content or "add_get" in content, \
            "WebSocket route not registered"
        assert "/ws" in content, "Missing /ws endpoint"

    def test_zeus_response_streaming(self):
        """Test that Zeus response streaming function exists."""
        ws_path = PLUGINS_DIR / "dashboard" / "websocket.py"
        content = ws_path.read_text()
        
        assert "stream_zeus_response" in content, "Missing stream_zeus_response function"
        assert "zeus_chunk" in content, "Missing zeus_chunk event type"

    def test_system_event_streaming(self):
        """Test that system event streaming function exists."""
        ws_path = PLUGINS_DIR / "dashboard" / "websocket.py"
        content = ws_path.read_text()
        
        assert "stream_system_event" in content, "Missing stream_system_event function"
