import sqlite3
import os
import pytest
from pathlib import Path

from tools.share_knowledge import ShareKnowledgeTool


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


@pytest.fixture
def tool(initialized_db):
    return ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)


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

    tool(
        action="write",
        scope="global",
        domain="contact",
        fact="John Doe - john@example.com",
    )

    delete_result = tool(
        action="delete",
        scope="global",
        domain="contact",
        fact="John Doe - john@example.com",
    )
    assert delete_result["status"] == "deleted"
    assert delete_result["rows_affected"] == 1

    query_result = tool(
        action="query",
        scope="global",
        domain="contact",
    )
    assert query_result["count"] == 0


def test_write_requires_fact(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    result = tool(
        action="write",
        scope="personal",
        domain="health",
        fact=None,
    )
    assert "error" in result


def test_multiple_facts_ordered(initialized_db):
    tool = ShareKnowledgeTool(db_path=initialized_db, allowed_scopes=None)

    tool(action="write", scope="personal", domain="health", fact="Fact 1")
    tool(action="write", scope="personal", domain="health", fact="Fact 2")
    tool(action="write", scope="personal", domain="health", fact="Fact 3")

    result = tool(action="query", scope="personal", domain="health", limit=2)
    assert result["count"] == 2
    assert result["facts"][0]["fact"] == "Fact 3"  # Most recent first
    assert result["facts"][1]["fact"] == "Fact 2"
