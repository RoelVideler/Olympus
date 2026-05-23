import sqlite3
import os
import pytest

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "olympus.db")

@pytest.fixture
def db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema", "001_initial.sql")
    with open(schema_path) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()

def test_knowledge_table_exists(db):
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='olympus_knowledge'"
    )
    assert result.fetchone() is not None

def test_agent_profiles_table_exists(db):
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_profiles'"
    )
    assert result.fetchone() is not None

def test_fts_table_exists(db):
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='olympus_knowledge_fts'"
    )
    assert result.fetchone() is not None

def test_insert_knowledge(db):
    db.execute(
        "INSERT INTO olympus_knowledge (id, scope, domain, fact, source_profile) VALUES (?, ?, ?, ?, ?)",
        ("test-1", "personal", "health", "User prefers morning calls", "zeus")
    )
    db.commit()
    result = db.execute("SELECT fact FROM olympus_knowledge WHERE id = 'test-1'")
    assert result.fetchone()[0] == "User prefers morning calls"

def test_fts_search(db):
    db.execute(
        "INSERT INTO olympus_knowledge (id, scope, domain, fact, source_profile) VALUES (?, ?, ?, ?, ?)",
        ("test-2", "business", "preference", "Client X prefers morning calls", "zeus")
    )
    db.commit()
    result = db.execute(
        "SELECT fact FROM olympus_knowledge_fts WHERE olympus_knowledge_fts MATCH 'morning'"
    )
    rows = result.fetchall()
    assert len(rows) >= 1

def test_scope_constraint(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO olympus_knowledge (id, scope, domain, fact, source_profile) VALUES (?, ?, ?, ?, ?)",
            ("test-3", "invalid_scope", "health", "test fact", "zeus")
        )
        db.commit()

def test_run_mode_constraint(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO agent_profiles (name, hermes_profile, run_mode) VALUES (?, ?, ?)",
            ("test", "test", "invalid_mode")
        )
        db.commit()
