# tests/test_iaso.py
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
        "iaso",
        "schema",
        "001_withings_sync.sql",
    )
    with open(schema_path) as f:
        return f.read()


@pytest.fixture
def initialized_db(db_path, schema_sql):
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()
    return db_path


class TestWithingsSchema:
    """Test that the withings_sync schema is correct."""

    def test_vitals_table_exists(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='withings_vitals'"
        )
        assert result.fetchone() is not None
        conn.close()

    def test_sleep_table_exists(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='withings_sleep'"
        )
        assert result.fetchone() is not None
        conn.close()

    def test_activity_table_exists(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='withings_activity'"
        )
        assert result.fetchone() is not None
        conn.close()

    def test_vitals_unique_constraint(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_vitals (id, userid, vitals_type, value, measured_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("v1", "u1", "weight", 75.0, "2026-05-25T10:00:00"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO withings_vitals (id, userid, vitals_type, value, measured_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("v2", "u1", "weight", 76.0, "2026-05-25T10:00:00"),
            )
            conn.commit()
        conn.close()

    def test_sleep_unique_constraint(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_sleep (id, userid, date)
               VALUES (?, ?, ?)""",
            ("s1", "u1", "2026-05-25"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO withings_sleep (id, userid, date)
                   VALUES (?, ?, ?)""",
                ("s2", "u1", "2026-05-25"),
            )
            conn.commit()
        conn.close()

    def test_activity_unique_constraint(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_activity (id, userid, date)
               VALUES (?, ?, ?)""",
            ("a1", "u1", "2026-05-25"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO withings_activity (id, userid, date)
                   VALUES (?, ?, ?)""",
                ("a2", "u1", "2026-05-25"),
            )
            conn.commit()
        conn.close()

    def test_vitals_synced_at_auto_populates(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_vitals (id, userid, vitals_type, value, measured_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("v-auto", "u1", "weight", 75.0, "2026-05-25T10:00:00"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT synced_at FROM withings_vitals WHERE id = 'v-auto'"
        ).fetchone()
        assert row[0] is not None
        assert "2026" in row[0] or "2025" in row[0]
        conn.close()

    def test_vitals_data_round_trip(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_vitals (id, userid, vitals_type, value, unit, measured_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("v-rt", "41770194", "weight", 75.5, "-3", "2026-05-25T10:00:00"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT userid, vitals_type, value, unit, measured_at FROM withings_vitals WHERE id = 'v-rt'"
        ).fetchone()
        assert row[0] == "41770194"
        assert row[1] == "weight"
        assert row[2] == 75.5
        assert row[3] == "-3"
        assert row[4] == "2026-05-25T10:00:00"
        conn.close()

    def test_sleep_data_round_trip(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_sleep (id, userid, date, sleep_score, total_sleep_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            ("s-rt", "41770194", "2026-05-25", 85, 28800),
        )
        conn.commit()
        row = conn.execute(
            "SELECT userid, date, sleep_score, total_sleep_seconds FROM withings_sleep WHERE id = 's-rt'"
        ).fetchone()
        assert row[0] == "41770194"
        assert row[1] == "2026-05-25"
        assert row[2] == 85
        assert row[3] == 28800
        conn.close()

    def test_activity_data_round_trip(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            """INSERT INTO withings_activity (id, userid, date, steps, calories)
               VALUES (?, ?, ?, ?, ?)""",
            ("a-rt", "41770194", "2026-05-25", 8773, 311.88),
        )
        conn.commit()
        row = conn.execute(
            "SELECT userid, date, steps, calories FROM withings_activity WHERE id = 'a-rt'"
        ).fetchone()
        assert row[0] == "41770194"
        assert row[1] == "2026-05-25"
        assert row[2] == 8773
        assert row[3] == 311.88
        conn.close()
