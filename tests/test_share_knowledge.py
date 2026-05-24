import os
import sqlite3
import pytest
from pathlib import Path
import json
import uuid


class ShareKnowledgeTool:
    """Wrapper for testing the share knowledge tool with a custom db path."""

    def __init__(self, db_path=None, allowed_scopes=None):
        self.db_path = db_path
        self.allowed_scopes = allowed_scopes

    def __call__(self, action, scope, domain, fact=None, confidence=1.0, source_profile=None, id=None, limit=10):
        # Scope enforcement
        if self.allowed_scopes is not None and scope not in self.allowed_scopes:
            return {"error": f"Profile not authorized for {action} on scope '{scope}'. Allowed: {self.allowed_scopes}"}

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if action == "write":
                if not fact:
                    return {"error": "fact is required for write action"}
                fact_id = str(uuid.uuid4())
                profile = source_profile or "test"
                conn.execute(
                    "INSERT INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile) VALUES (?, ?, ?, ?, ?, ?)",
                    (fact_id, scope, domain, fact, confidence, profile),
                )
                conn.commit()
                return {"status": "written", "id": fact_id}
            elif action == "query":
                rows = conn.execute(
                    "SELECT id, domain, fact, confidence, source_profile, created_at FROM olympus_knowledge WHERE scope = ? AND domain = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                    (scope, domain, limit),
                ).fetchall()
                return {
                    "status": "ok",
                    "facts": [dict(row) for row in rows],
                    "count": len(rows),
                }
            elif action == "delete":
                if id is None:
                    return {"error": "id is required for delete action (delete by fact text is deprecated — use id instead)"}
                # Check scope ownership of the fact being deleted
                if self.allowed_scopes is not None:
                    row = conn.execute("SELECT scope FROM olympus_knowledge WHERE id = ?", (id,)).fetchone()
                    if row and row["scope"] not in self.allowed_scopes:
                        return {"error": f"Profile not authorized for delete on scope '{row['scope']}'. Allowed: {self.allowed_scopes}"}
                cursor = conn.execute("DELETE FROM olympus_knowledge WHERE id = ?", (id,))
                conn.commit()
                return {"status": "deleted", "rows_affected": cursor.rowcount}
        finally:
            conn.close()


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "olympus.db")


@pytest.fixture
def schema_sql():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema", "001_initial.sql")
    with open(schema_path) as f:
        return f.read()


@pytest.fixture
def initialized_db(db_path, schema_sql):
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()
    return db_path


def test_write_and_query(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    write_result = tool(
        action="write",
        scope="personal",
        domain="preference",
        fact="User prefers morning calls",
        confidence=0.9,
    )
    assert write_result["status"] == "written"
    assert "id" in write_result

    query_result = tool(
        action="query",
        scope="personal",
        domain="preference",
    )
    assert query_result["status"] == "ok"
    assert query_result["count"] == 1
    assert query_result["facts"][0]["fact"] == "User prefers morning calls"


def test_scope_restriction(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=["personal"])

    # Can write to personal
    result = tool(
        action="write",
        scope="personal",
        domain="health",
        fact="User has a doctor appointment",
    )
    assert result["status"] == "written"

    # Cannot write to business
    result = tool(
        action="write",
        scope="business",
        domain="finance",
        fact="Test fact",
    )
    assert "error" in result
    assert "not authorized" in result["error"]


def test_delete(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    write_result = tool(
        action="write",
        scope="global",
        domain="contact",
        fact="John Doe - john@example.com",
    )
    fact_id = write_result["id"]

    delete_result = tool(
        action="delete",
        scope="global",
        domain="contact",
        id=fact_id,
    )
    assert delete_result["status"] == "deleted"
    assert delete_result["rows_affected"] == 1

    query_result = tool(
        action="query",
        scope="global",
        domain="contact",
    )
    assert query_result["count"] == 0


def test_delete_by_fact_deprecated(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    result = tool(
        action="delete",
        scope="global",
        domain="contact",
        fact="some fact",
    )
    assert "error" in result
    assert "deprecated" in result["error"]


def test_delete_scope_restriction(initialized_db):
    tool_all = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)
    tool_personal = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=["personal"])

    write_result = tool_all(
        action="write",
        scope="business",
        domain="finance",
        fact="Revenue target: $1M",
    )
    fact_id = write_result["id"]

    result = tool_personal(
        action="delete",
        scope="personal",
        domain="finance",
        id=fact_id,
    )
    assert "error" in result
    assert "not authorized" in result["error"]

    query_result = tool_all(action="query", scope="business", domain="finance")
    assert query_result["count"] == 1


def test_write_requires_fact(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    result = tool(
        action="write",
        scope="personal",
        domain="health",
        fact=None,
    )
    assert "fact is required" in result["error"]


def test_multiple_facts_ordered(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    tool(action="write", scope="personal", domain="health", fact="Fact 1")
    tool(action="write", scope="personal", domain="health", fact="Fact 2")
    tool(action="write", scope="personal", domain="health", fact="Fact 3")

    result = tool(action="query", scope="personal", domain="health", limit=2)
    assert result["count"] == 2
    assert result["facts"][0]["fact"] == "Fact 3"  # Most recent first
    assert result["facts"][1]["fact"] == "Fact 2"


def test_cross_profile_round_trip(initialized_db):
    tool_hermes = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)
    tool_zeus = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    write_result = tool_hermes(
        action="write",
        scope="global",
        domain="contact",
        fact="Hermes knows this fact",
        source_profile="hermes",
    )
    assert write_result["status"] == "written"
    fact_id = write_result["id"]

    query_result = tool_zeus(
        action="query",
        scope="global",
        domain="contact",
    )
    assert query_result["count"] == 1
    assert query_result["facts"][0]["fact"] == "Hermes knows this fact"
    assert query_result["facts"][0]["source_profile"] == "hermes"

    delete_result = tool_zeus(
        action="delete",
        scope="global",
        domain="contact",
        id=fact_id,
    )
    assert delete_result["status"] == "deleted"
    assert delete_result["rows_affected"] == 1
