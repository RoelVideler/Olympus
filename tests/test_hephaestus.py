import json
import sqlite3
import os
import pytest
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "olympus.db")


@pytest.fixture
def schema_sql():
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "plugins",
        "hephaestus",
        "schema",
        "001_home_maintenance.sql",
    )
    with open(schema_path) as f:
        return f.read()


@pytest.fixture
def initialized_db(db_path, schema_sql):
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()
    return db_path


class TestHomeMaintenanceSchema:
    """Test that the home_maintenance schema is correct."""

    def test_table_exists(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='home_maintenance'"
        )
        assert result.fetchone() is not None
        conn.close()

    def test_insert_maintenance_record(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """
            INSERT INTO home_maintenance (id, device, domain, action, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test-1", "HVAC", "hvac", "filter_replaced", "Replaced with MERV 11"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT device, domain, action, notes FROM home_maintenance WHERE id = 'test-1'"
        ).fetchone()
        assert row is not None
        assert row[0] == "HVAC"
        assert row[1] == "hvac"
        assert row[2] == "filter_replaced"
        assert row[3] == "Replaced with MERV 11"
        conn.close()

    def test_scheduled_date_nullable(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """
            INSERT INTO home_maintenance (id, device, domain, action, scheduled_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test-2", "HVAC", "hvac", "filter_replace", "2026-06-15"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT scheduled_date FROM home_maintenance WHERE id = 'test-2'"
        ).fetchone()
        assert row[0] == "2026-06-15"
        conn.close()

    def test_recurrence_days_nullable(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        # One-time record (no recurrence)
        conn.execute(
            """
            INSERT INTO home_maintenance (id, device, domain, action)
            VALUES (?, ?, ?, ?)
            """,
            ("test-3", "Roof", "structural", "inspection"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT recurrence_days FROM home_maintenance WHERE id = 'test-3'"
        ).fetchone()
        assert row[0] is None
        conn.close()

    def test_created_at_auto_populates(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """
            INSERT INTO home_maintenance (id, device, domain, action)
            VALUES (?, ?, ?, ?)
            """,
            ("test-4", "HVAC", "hvac", "inspection"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at FROM home_maintenance WHERE id = 'test-4'"
        ).fetchone()
        assert row[0] is not None
        # Verify it's a valid datetime string
        assert "2026" in row[0] or "2025" in row[0]
        conn.close()

    def test_completed_date_stored(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """
            INSERT INTO home_maintenance (id, device, domain, action, completed_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test-5", "HVAC", "hvac", "filter_replaced", "2026-05-20"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT completed_date FROM home_maintenance WHERE id = 'test-5'"
        ).fetchone()
        assert row[0] == "2026-05-20"
        conn.close()


import plugins.hephaestus.skills.home_maintenance as home_maintenance
from plugins.hephaestus.skills.home_maintenance import handle_home_maintenance


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use temp database for tests."""
    db = tmp_path / "olympus.db"
    # Create schema first
    conn = sqlite3.connect(str(db))
    schema_path = Path(__file__).parent.parent / "plugins" / "hephaestus" / "schema" / "001_home_maintenance.sql"
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
    monkeypatch.setattr(home_maintenance, "_DB_PATH", db)
    yield


class TestLogMaintenance:
    """Test logging maintenance events."""

    def test_log_minimal(self):
        result = handle_home_maintenance({
            "action": "log_maintenance",
            "device": "HVAC",
            "action_type": "filter_replaced",
        })
        data = json.loads(result)
        assert data["status"] == "logged"
        assert data["device"] == "HVAC"
        assert "id" in data

    def test_log_with_notes(self):
        result = handle_home_maintenance({
            "action": "log_maintenance",
            "device": "Dishwasher",
            "domain": "appliance",
            "action_type": "repair",
            "notes": "Replaced door latch",
        })
        data = json.loads(result)
        assert data["status"] == "logged"

    def test_log_requires_device(self):
        result = handle_home_maintenance({
            "action": "log_maintenance",
            "action_type": "inspection",
        })
        data = json.loads(result)
        assert "error" in data
        assert "device" in data["error"]

    def test_log_requires_action_type(self):
        result = handle_home_maintenance({
            "action": "log_maintenance",
            "device": "HVAC",
        })
        data = json.loads(result)
        assert "error" in data
        assert "action_type" in data["error"]


class TestQueryMaintenance:
    """Test querying maintenance history."""

    def test_query_all(self):
        handle_home_maintenance({
            "action": "log_maintenance",
            "device": "HVAC",
            "action_type": "filter_replaced",
        })
        result = handle_home_maintenance({"action": "query_maintenance"})
        data = json.loads(result)
        assert data["count"] >= 1

    def test_query_by_device(self):
        handle_home_maintenance({
            "action": "log_maintenance",
            "device": "HVAC",
            "action_type": "filter_replaced",
        })
        handle_home_maintenance({
            "action": "log_maintenance",
            "device": "Dishwasher",
            "action_type": "repair",
        })
        result = handle_home_maintenance({
            "action": "query_maintenance",
            "device": "HVAC",
        })
        data = json.loads(result)
        assert data["count"] == 1
        assert data["records"][0]["device"] == "HVAC"

    def test_query_by_domain(self):
        handle_home_maintenance({
            "action": "log_maintenance",
            "device": "HVAC",
            "domain": "hvac",
            "action_type": "filter_replaced",
        })
        handle_home_maintenance({
            "action": "log_maintenance",
            "device": "Dishwasher",
            "domain": "appliance",
            "action_type": "repair",
        })
        result = handle_home_maintenance({
            "action": "query_maintenance",
            "domain": "hvac",
        })
        data = json.loads(result)
        assert data["count"] == 1

    def test_query_respects_limit(self):
        for i in range(5):
            handle_home_maintenance({
                "action": "log_maintenance",
                "device": f"Device-{i}",
                "action_type": "inspection",
            })
        result = handle_home_maintenance({
            "action": "query_maintenance",
            "limit": 2,
        })
        data = json.loads(result)
        assert data["count"] == 2


class TestScheduleReminder:
    """Test scheduling maintenance reminders."""

    def test_schedule_reminder(self):
        result = handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
            "recurrence_days": 90,
        })
        data = json.loads(result)
        assert data["status"] == "scheduled"
        assert data["recurrence_days"] == 90

    def test_schedule_requires_device(self):
        result = handle_home_maintenance({
            "action": "schedule_reminder",
            "action_type": "filter_replace",
            "recurrence_days": 90,
        })
        data = json.loads(result)
        assert "error" in data

    def test_schedule_requires_recurrence(self):
        result = handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
        })
        data = json.loads(result)
        assert "error" in data


class TestQueryReminders:
    """Test querying maintenance reminders."""

    def test_query_no_reminders(self):
        result = handle_home_maintenance({"action": "query_reminders"})
        data = json.loads(result)
        assert data["count"] == 0
        assert data["overdue_count"] == 0

    def test_query_reminders_returns_scheduled(self):
        handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
            "recurrence_days": 90,
            "scheduled_date": "2026-06-01",
        })
        result = handle_home_maintenance({"action": "query_reminders"})
        data = json.loads(result)
        assert data["count"] == 1
        assert data["reminders"][0]["device"] == "HVAC"

    def test_overdue_reminder_detected(self):
        handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
            "recurrence_days": 90,
            "scheduled_date": "2020-01-01",
        })
        result = handle_home_maintenance({
            "action": "query_reminders",
            "overdue_only": True,
        })
        data = json.loads(result)
        assert data["overdue_count"] == 1
        assert data["reminders"][0]["is_overdue"] is True

    def test_completed_reminder_no_longer_overdue(self):
        """A reminder with a completed_date in the past should not be overdue."""
        handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
            "recurrence_days": 90,
            "scheduled_date": "2020-01-01",
        })
        # Query to get the reminder ID
        result = handle_home_maintenance({"action": "query_reminders"})
        data = json.loads(result)
        reminder_id = data["reminders"][0]["id"]

        # Mark the reminder as completed by updating its completed_date
        conn = sqlite3.connect(str(home_maintenance._DB_PATH))
        conn.execute(
            "UPDATE home_maintenance SET completed_date = ? WHERE id = ?",
            ("2026-05-26", reminder_id),
        )
        conn.commit()
        conn.close()

        # Now query overdue reminders — should be 0
        result = handle_home_maintenance({
            "action": "query_reminders",
            "overdue_only": True,
        })
        data = json.loads(result)
        assert data["overdue_count"] == 0

    def test_recurrence_calculates_next_date(self):
        handle_home_maintenance({
            "action": "schedule_reminder",
            "device": "HVAC",
            "action_type": "filter_replace",
            "recurrence_days": 90,
            "scheduled_date": "2026-01-01",
        })
        result = handle_home_maintenance({"action": "query_reminders"})
        data = json.loads(result)
        reminder = data["reminders"][0]
        assert reminder["next_due"] == "2026-01-01"


class TestShareFact:
    """Test sharing facts to cross-agent knowledge."""

    def test_share_fact_requires_fact(self):
        result = handle_home_maintenance({"action": "share_fact"})
        data = json.loads(result)
        assert "error" in data

    def test_share_fact_returns_local_fallback(self):
        """When share_knowledge is not available, returns local fallback."""
        result = handle_home_maintenance({
            "action": "share_fact",
            "fact": "HVAC filter replaced on 2026-05-25",
            "domain": "home",
        })
        data = json.loads(result)
        assert data["status"] in ("shared", "shared_local")


class TestHomeMaintenanceErrors:
    """Test error handling."""

    def test_unknown_action(self):
        result = handle_home_maintenance({"action": "nonexistent"})
        data = json.loads(result)
        assert "error" in data
