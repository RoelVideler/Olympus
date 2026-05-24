"""Tests for the share_knowledge plugin — tests actual production code.

These tests import and exercise `_handle_share_knowledge` from
`plugins/share_knowledge/tools.py`, not a duplicated inline wrapper.
"""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# Import actual production code
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from plugins.share_knowledge.tools import (
    _handle_share_knowledge,
    _get_db,
    _ensure_schema,
    SHARE_KNOWLEDGE_SCHEMA,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "olympus.db")


@pytest.fixture
def schema_sql():
    schema_path = PROJECT_ROOT / "schema" / "001_initial.sql"
    with open(schema_path) as f:
        return f.read()


@pytest.fixture
def initialized_db(db_path, schema_sql):
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()
    return db_path


def _call(action, scope, domain, db_path, scope_config=None, **kwargs):
    """Helper that calls the actual production handler with a custom db path."""
    args = {"action": action, "scope": scope, "domain": domain, **kwargs}
    with patch("plugins.share_knowledge.tools.DEFAULT_DB_PATH", Path(db_path)):
        result = _handle_share_knowledge(args, scope_config=scope_config)
    return json.loads(result)


# ============================================================
# Write and query
# ============================================================

def test_write_and_query(initialized_db):
    write_result = _call(
        "write", "personal", "preference",
        db_path=initialized_db,
        fact="User prefers morning calls",
        confidence=0.9,
    )
    assert write_result["status"] == "written"
    assert "id" in write_result

    query_result = _call(
        "query", "personal", "preference",
        db_path=initialized_db,
    )
    assert query_result["status"] == "ok"
    assert query_result["count"] == 1
    assert query_result["facts"][0]["fact"] == "User prefers morning calls"


# ============================================================
# Scope enforcement
# ============================================================

def test_scope_restriction_write(initialized_db):
    scope_config = {
        "default": {"read": ["personal"], "write": ["personal"]},
    }
    # Can write to personal
    result = _call(
        "write", "personal", "health",
        db_path=initialized_db,
        scope_config=scope_config,
        fact="User has a doctor appointment",
    )
    assert result["status"] == "written"

    # Cannot write to business
    result = _call(
        "write", "business", "finance",
        db_path=initialized_db,
        scope_config=scope_config,
        fact="Test fact",
    )
    assert "error" in result
    assert "not authorized" in result["error"]


def test_scope_restriction_query(initialized_db):
    scope_config = {
        "default": {"read": ["personal"], "write": ["personal"]},
    }
    # Write a fact first (no scope config)
    _call("write", "business", "finance", db_path=initialized_db, fact="Revenue target")

    # Query with restricted scope — should be denied
    result = _call(
        "query", "business", "finance",
        db_path=initialized_db,
        scope_config=scope_config,
    )
    assert "error" in result
    assert "not authorized" in result["error"]


# ============================================================
# Delete
# ============================================================

def test_delete(initialized_db):
    write_result = _call(
        "write", "global", "contact",
        db_path=initialized_db,
        fact="John Doe - john@example.com",
    )
    fact_id = write_result["id"]

    delete_result = _call(
        "delete", "global", "contact",
        db_path=initialized_db,
        id=fact_id,
    )
    assert delete_result["status"] == "deleted"
    assert delete_result["rows_affected"] == 1

    query_result = _call("query", "global", "contact", db_path=initialized_db)
    assert query_result["count"] == 0


def test_delete_by_fact_deprecated(initialized_db):
    result = _call(
        "delete", "global", "contact",
        db_path=initialized_db,
        fact="some fact",
    )
    assert "error" in result
    assert "deprecated" in result["error"]


def test_delete_scope_restriction(initialized_db):
    scope_config = {
        "default": {"read": ["personal"], "write": ["personal"]},
    }
    # Write a business fact (no scope config)
    write_result = _call(
        "write", "business", "finance",
        db_path=initialized_db,
        fact="Revenue target: $1M",
    )
    fact_id = write_result["id"]

    # Try to delete with restricted scope
    result = _call(
        "delete", "personal", "finance",
        db_path=initialized_db,
        scope_config=scope_config,
        id=fact_id,
    )
    assert "error" in result
    assert "not authorized" in result["error"]

    # Fact still exists
    query_result = _call("query", "business", "finance", db_path=initialized_db)
    assert query_result["count"] == 1


# ============================================================
# Validation
# ============================================================

def test_write_requires_fact(initialized_db):
    result = _call(
        "write", "personal", "health",
        db_path=initialized_db,
    )
    assert "error" in result
    assert "fact is required" in result["error"]


def test_delete_requires_id(initialized_db):
    result = _call(
        "delete", "global", "contact",
        db_path=initialized_db,
    )
    assert "error" in result
    assert "id is required" in result["error"]


def test_unknown_action(initialized_db):
    result = _call(
        "foobar", "personal", "health",
        db_path=initialized_db,
    )
    assert "error" in result
    assert "Unknown action" in result["error"]


def test_unknown_scope(initialized_db):
    result = _call(
        "write", "invalid_scope", "health",
        db_path=initialized_db,
        fact="test",
    )
    assert "error" in result
    assert "Unknown scope" in result["error"]


def test_domain_too_long(initialized_db):
    result = _call(
        "write", "personal", "x" * 101,
        db_path=initialized_db,
        fact="test",
    )
    assert "error" in result
    assert "too long" in result["error"]


def test_fact_too_long(initialized_db):
    result = _call(
        "write", "personal", "health",
        db_path=initialized_db,
        fact="x" * 10001,
    )
    assert "error" in result
    assert "too long" in result["error"]


# ============================================================
# Ordering and limits
# ============================================================

def test_multiple_facts_ordered(initialized_db):
    _call("write", "personal", "health", db_path=initialized_db, fact="Fact 1")
    _call("write", "personal", "health", db_path=initialized_db, fact="Fact 2")
    _call("write", "personal", "health", db_path=initialized_db, fact="Fact 3")

    result = _call("query", "personal", "health", db_path=initialized_db, limit=2)
    assert result["count"] == 2
    assert result["facts"][0]["fact"] == "Fact 3"  # Most recent first
    assert result["facts"][1]["fact"] == "Fact 2"


# ============================================================
# Cross-profile round trip
# ============================================================

def test_cross_profile_round_trip(initialized_db):
    write_result = _call(
        "write", "global", "contact",
        db_path=initialized_db,
        fact="Hermes knows this fact",
    )
    assert write_result["status"] == "written"
    fact_id = write_result["id"]

    query_result = _call("query", "global", "contact", db_path=initialized_db)
    assert query_result["count"] == 1
    assert query_result["facts"][0]["fact"] == "Hermes knows this fact"
    assert query_result["facts"][0]["source_profile"] == "default"  # No Hermes context in tests

    delete_result = _call(
        "delete", "global", "contact",
        db_path=initialized_db,
        id=fact_id,
    )
    assert delete_result["status"] == "deleted"
    assert delete_result["rows_affected"] == 1


# ============================================================
# Plugin registration
# ============================================================

def test_plugin_imports_without_error():
    """The plugin module should import without ImportError."""
    from plugins.share_knowledge import register, SHARE_KNOWLEDGE_SCHEMA as SPEC
    assert register is not None
    assert SPEC is not None


def test_plugin_has_register_function():
    """The plugin must expose a register(ctx) function."""
    from plugins.share_knowledge import register
    assert callable(register)


def test_schema_is_valid():
    """SHARE_KNOWLEDGE_SCHEMA must be a valid tool schema."""
    assert "type" in SHARE_KNOWLEDGE_SCHEMA or "function" in SHARE_KNOWLEDGE_SCHEMA
    schema = SHARE_KNOWLEDGE_SCHEMA.get("function", SHARE_KNOWLEDGE_SCHEMA)
    assert schema["name"] == "share_knowledge"
    assert "parameters" in schema
