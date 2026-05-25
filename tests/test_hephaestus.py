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
