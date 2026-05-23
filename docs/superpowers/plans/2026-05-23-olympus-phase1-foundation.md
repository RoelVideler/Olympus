# Olympus Phase 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install Hermes Agent, create 10 agent profiles, set up shared SQLite with `share_knowledge` tool, and verify all profiles boot independently.

**Architecture:** Each Olympus agent runs as a Hermes Agent profile with isolated config, memory, and tools. Cross-agent knowledge flows through a shared SQLite database via a `share_knowledge` Hermes tool plugin. Communication between profiles uses Hermes' native ACP/MCP interfaces.

**Tech Stack:** Hermes Agent (Nous Research), Python 3.11+, SQLite, pytest

---

## File Structure

```
Olympus/
├── profiles/                    # Hermes profile configs per agent
│   ├── zeus/config.yaml
│   ├── chronos/config.yaml
│   ├── iaso/config.yaml
│   ├── hermes-agent/config.yaml   # renamed from "hermes" to avoid collision
│   ├── philia/config.yaml
│   ├── plutus/config.yaml
│   ├── hephaestus/config.yaml
│   ├── metis/config.yaml
│   ├── apollo/config.yaml
│   └── midas/config.yaml
├── tools/                       # Custom Hermes tool plugins
│   └── share_knowledge/
│       ├── __init__.py
│       └── tool.py
├── schema/                      # SQLite schema
│   └── 001_initial.sql
├── tests/                       # Phase 1 tests
│   ├── test_share_knowledge.py
│   └── test_profile_boot.py
├── scripts/                     # Setup and verification scripts
│   ├── setup_hermes.py
│   └── verify_profiles.py
├── docs/
│   └── 2026-05-23-olympus-architecture-design.md
├── pyproject.toml
└── README.md
```

---

### Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `profiles/` directory structure
- Create: `tools/` directory structure
- Create: `schema/` directory
- Create: `tests/` directory
- Create: `scripts/` directory

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "olympus"
version = "0.1.0"
description = "Personal AI life assistant — built on Hermes Agent"
requires-python = ">=3.11"
dependencies = [
    "hermes-agent",  # Nous Research Hermes Agent
    "pytest>=7.0",
]

[project.optional-dependencies]
dev = [
    "pytest",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create README.md**

```markdown
# Olympus

Personal AI life assistant built on Nous Research's Hermes Agent.

## Phase 1: Foundation

- Hermes Agent installed and configured
- 10 agent profiles created
- Shared SQLite database with `share_knowledge` tool
- All profiles boot independently

## Setup

```bash
pip install -e .
```

## Run Tests

```bash
pytest tests/ -v
```
```

- [ ] **Step 3: Create directory structure**

```bash
mkdir -p profiles/{zeus,chronos,iaso,hermes-agent,philia,plutus,hephaestus,metis,apollo,midas}
mkdir -p tools/share_knowledge
mkdir -p schema
mkdir -p tests
mkdir -p scripts
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: Olympus Phase 1 project skeleton"
```

---

### Task 2: Hermes Agent Installation and Discovery

**Files:**
- Create: `scripts/setup_hermes.py`
- Modify: `README.md` (add Hermes setup instructions)

**Note:** This task includes discovery steps because we need to understand Hermes Agent's actual capabilities. Document findings as you go.

- [ ] **Step 1: Install Hermes Agent**

```bash
pip install hermes-agent
```

If the package name is different, search for it:
```bash
pip search hermes-agent  # or check Nous Research's GitHub
```

- [ ] **Step 2: Verify Hermes installation**

```bash
hermes --help
hermes --version
```

Record the version and available commands in `scripts/setup_hermes.py` as comments.

- [ ] **Step 3: Explore Hermes CLI**

Run these commands and document outputs in `scripts/setup_hermes.py`:

```bash
hermes --help
hermes init --help
hermes -p test --help  # profile-specific help
hermes list-profiles  # or equivalent
```

- [ ] **Step 4: Explore Hermes ACP/MCP interfaces**

Check for ACP and MCP support:

```bash
# Check for ACP
hermes acp --help  # or look for acp in --help output

# Check for MCP
hermes mcp --help  # or look for mcp in --help output
hermes mcp serve --help
```

Also check the Hermes source code for ACP/MCP:
```bash
python -c "import hermes; print(hermes.__file__)"
# Then explore the package directory for acp/, mcp/, or similar
```

Document findings in `scripts/setup_hermes.py`:
- Does Hermes have ACP? What's the interface?
- Does Hermes have MCP? What's the interface?
- How does Zeus communicate with profiles?
- What's the actual command to run a profile?

- [ ] **Step 5: Explore Hermes profile system**

```bash
# Create a test profile
hermes init -p test-profile

# Examine the profile structure
ls -la ~/.hermes/test-profile/  # or wherever profiles are stored
cat ~/.hermes/test-profile/config.yaml
```

Document the profile structure in `scripts/setup_hermes.py`.

- [ ] **Step 6: Explore Hermes tool plugin system**

Check how custom tools are registered:

```bash
# Look for tool registration in Hermes source
python -c "import hermes; import os; print(os.path.dirname(hermes.__file__))"
# Then explore tools/ directory in the Hermes package
```

Document:
- How are custom tools registered?
- What's the tool plugin interface?
- How does Hermes discover tools?

- [ ] **Step 7: Explore Hermes cron system**

```bash
hermes job --help  # or equivalent
```

Document how cron jobs are configured.

- [ ] **Step 8: Commit findings**

```bash
git add scripts/setup_hermes.py
git commit -m "docs: Hermes Agent installation and discovery findings"
```

---

### Task 3: SQLite Schema

**Files:**
- Create: `schema/001_initial.sql`
- Create: `tests/test_schema.py`

- [ ] **Step 1: Write the schema SQL**

```sql
-- schema/001_initial.sql
-- Olympus cross-agent knowledge schema (SQLite + FTS5)

-- Shared facts that any agent can read/write
CREATE TABLE IF NOT EXISTS olympus_knowledge (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('personal', 'business', 'global')),
    domain TEXT NOT NULL,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    source_profile TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS olympus_knowledge_fts USING fts5(
    fact, domain, scope,
    content='olympus_knowledge',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS olympus_knowledge_ai AFTER INSERT ON olympus_knowledge BEGIN
    INSERT INTO olympus_knowledge_fts(rowid, fact, domain, scope)
    VALUES (new.rowid, new.fact, new.domain, new.scope);
END;

CREATE TRIGGER IF NOT EXISTS olympus_knowledge_ad AFTER DELETE ON olympus_knowledge BEGIN
    DELETE FROM olympus_knowledge_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS olympus_knowledge_au AFTER UPDATE ON olympus_knowledge BEGIN
    UPDATE olympus_knowledge_fts
    SET fact = new.fact, domain = new.domain, scope = new.scope
    WHERE rowid = new.rowid;
END;

-- Agent registry
CREATE TABLE IF NOT EXISTS agent_profiles (
    name TEXT PRIMARY KEY,
    hermes_profile TEXT NOT NULL,
    run_mode TEXT NOT NULL DEFAULT 'on-demand' CHECK(run_mode IN ('always-on', 'on-demand', 'cron-only')),
    model_provider TEXT,
    model_name TEXT,
    status TEXT DEFAULT 'stopped' CHECK(status IN ('stopped', 'running', 'error'))
);
```

- [ ] **Step 2: Write schema test**

```python
# tests/test_schema.py
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
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
pytest tests/test_schema.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add schema/001_initial.sql tests/test_schema.py
git commit -m "feat: SQLite schema with FTS5 and constraints"
```

---

### Task 4: share_knowledge Tool Plugin

**Files:**
- Create: `tools/share_knowledge/__init__.py`
- Create: `tools/share_knowledge/tool.py`
- Create: `tests/test_share_knowledge.py`

- [ ] **Step 1: Write the tool plugin**

```python
# tools/share_knowledge/__init__.py
from .tool import ShareKnowledgeTool

__all__ = ["ShareKnowledgeTool"]
```

```python
# tools/share_knowledge/tool.py
"""
share_knowledge: Cross-agent knowledge tool for Olympus.

Reads/writes shared facts from the Olympus SQLite database.
Scope access is enforced in application logic: each agent's tool config
specifies which scopes it can read and write.
"""
import sqlite3
import uuid
from typing import Literal
from pathlib import Path


class ShareKnowledgeTool:
    """Hermes tool plugin for cross-agent knowledge sharing."""

    name = "share_knowledge"
    description = "Write, query, or delete cross-agent knowledge facts."

    def __init__(self, db_path: str | Path, allowed_scopes: list[str] | None = None):
        """
        Args:
            db_path: Path to the shared SQLite database.
            allowed_scopes: List of scopes this agent can access.
                           None means all scopes (for Zeus).
        """
        self.db_path = Path(db_path)
        self.allowed_scopes = allowed_scopes  # None = all scopes

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _check_scope(self, scope: str):
        if self.allowed_scopes is not None and scope not in self.allowed_scopes:
            raise PermissionError(
                f"Agent not authorized for scope '{scope}'. Allowed: {self.allowed_scopes}"
            )

    def __call__(
        self,
        action: Literal["write", "query", "delete"],
        scope: Literal["personal", "business", "global"],
        domain: str,
        fact: str | None = None,
        confidence: float = 1.0,
        limit: int = 10,
    ) -> dict:
        """Execute a share_knowledge action."""
        self._check_scope(scope)

        if action == "write":
            return self._write(scope, domain, fact, confidence)
        elif action == "query":
            return self._query(scope, domain, limit)
        elif action == "delete":
            return self._delete(scope, domain, fact)
        else:
            return {"error": f"Unknown action: {action}"}

    def _write(self, scope: str, domain: str, fact: str, confidence: float) -> dict:
        if not fact:
            return {"error": "fact is required for write action"}

        conn = self._connect()
        try:
            fact_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (fact_id, scope, domain, fact, confidence, "current_agent"),
            )
            conn.commit()
            return {"status": "written", "id": fact_id}
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def _query(self, scope: str, domain: str, limit: int) -> dict:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT id, domain, fact, confidence, source_profile, created_at
                FROM olympus_knowledge
                WHERE scope = ? AND domain = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (scope, domain, limit),
            ).fetchall()

            return {
                "status": "ok",
                "facts": [
                    {
                        "id": row["id"],
                        "domain": row["domain"],
                        "fact": row["fact"],
                        "confidence": row["confidence"],
                        "source_profile": row["source_profile"],
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ],
                "count": len(rows),
            }
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def _delete(self, scope: str, domain: str, fact: str | None) -> dict:
        if not fact:
            return {"error": "fact is required for delete action"}

        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM olympus_knowledge WHERE scope = ? AND domain = ? AND fact = ?",
                (scope, domain, fact),
            )
            conn.commit()
            return {"status": "deleted", "rows_affected": cursor.rowcount}
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()
```

- [ ] **Step 2: Write tests**

```python
# tests/test_share_knowledge.py
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
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
pytest tests/test_share_knowledge.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tools/share_knowledge/ tests/test_share_knowledge.py
git commit -m "feat: share_knowledge tool plugin with scope enforcement"
```

---

### Task 5: Profile Configurations

**Files:**
- Create: `profiles/zeus/config.yaml`
- Create: `profiles/chronos/config.yaml`
- Create: `profiles/iaso/config.yaml`
- Create: `profiles/hermes-agent/config.yaml`
- Create: `profiles/philia/config.yaml`
- Create: `profiles/plutus/config.yaml`
- Create: `profiles/hephaestus/config.yaml`
- Create: `profiles/metis/config.yaml`
- Create: `profiles/apollo/config.yaml`
- Create: `profiles/midas/config.yaml`

**Note:** The exact config format depends on Hermes Agent's profile system. Use the discovery findings from Task 2. The configs below are templates — adjust based on actual Hermes requirements.

- [ ] **Step 1: Create Zeus config**

```yaml
# profiles/zeus/config.yaml
# Zeus: Front-door orchestrator — routing, workflow, tone, chip-in coordination
profile:
  name: zeus
  run_mode: always-on

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-35b-a3b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser

memory:
  session_store: true
  memory_files:
    - MEMORY.md
    - USER.md
```

- [ ] **Step 2: Create Chronos config**

```yaml
# profiles/chronos/config.yaml
# Chronos: Scheduling, calendar, energy-aware planning
profile:
  name: chronos
  run_mode: always-on

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - calendar_query
    - web_search
  block:
    - terminal
    - browser
```

- [ ] **Step 3: Create Iaso config**

```yaml
# profiles/iaso/config.yaml
# Iaso: Health, symptoms, vitals, Withings sync
profile:
  name: iaso
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - withings_sync
    - web_search
  block:
    - terminal
    - browser
    # Block filesystem-write for sensitive data profile
```

- [ ] **Step 4: Create Hermes (messenger) config**

```yaml
# profiles/hermes-agent/config.yaml
# Hermes: Messenger — email triage, WhatsApp, contact forms
profile:
  name: hermes-agent
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - gmail_triage
    - whatsapp_send
    - web_search
  block:
    - terminal
    - browser
```

- [ ] **Step 5: Create remaining configs (Philia, Plutus, Hephaestus, Metis, Apollo, Midas)**

```yaml
# profiles/philia/config.yaml
# Philia: Relationships, social obligations
profile:
  name: philia
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser
```

```yaml
# profiles/plutus/config.yaml
# Plutus: Personal investments, portfolio
profile:
  name: plutus
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser
```

```yaml
# profiles/hephaestus/config.yaml
# Hephaestus: Home automation, devices, maintenance
profile:
  name: hephaestus
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - home_assistant
    - web_search
  block:
    - terminal
    - browser
```

```yaml
# profiles/metis/config.yaml
# Metis: Business domain expert — markets, practices, development strategy
profile:
  name: metis
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-35b-a3b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser
```

```yaml
# profiles/apollo/config.yaml
# Apollo: Creative — photography, art, events
profile:
  name: apollo
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser
```

```yaml
# profiles/midas/config.yaml
# Midas: Finance — invoicing, expenses, budget
profile:
  name: midas
  run_mode: on-demand

llm:
  provider: openai-compatible
  base_url: http://localhost:11434/v1
  model: qwen3.6-8b

tools:
  allow:
    - share_knowledge
    - web_search
  block:
    - terminal
    - browser
```

- [ ] **Step 6: Commit**

```bash
git add profiles/
git commit -m "feat: 10 Hermes profile configurations"
```

---

### Task 6: Profile Boot Verification

**Files:**
- Create: `scripts/verify_profiles.py`
- Create: `tests/test_profile_boot.py`

- [ ] **Step 1: Write verification script**

```python
#!/usr/bin/env python3
"""
verify_profiles.py: Verify all 10 Hermes profiles boot and respond.

Usage:
    python scripts/verify_profiles.py

Expected output:
    zeus: OK (response time: X.XXs)
    chronos: OK (response time: X.XXs)
    ...
"""
import subprocess
import time
import sys

PROFILES = [
    "zeus",
    "chronos",
    "iaso",
    "hermes-agent",
    "philia",
    "plutus",
    "hephaestus",
    "metis",
    "apollo",
    "midas",
]

TEST_PROMPT = "Who are you? Respond in one sentence."


def verify_profile(profile_name: str) -> tuple[bool, str]:
    """Verify a single profile boots and responds."""
    start = time.time()
    try:
        # Use Hermes' actual CLI command to run a profile with a prompt
        # This will need to be adjusted based on Hermes' actual interface
        result = subprocess.run(
            ["hermes", "-p", profile_name, "-z", TEST_PROMPT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start

        if result.returncode == 0 and result.stdout.strip():
            return True, f"OK ({elapsed:.2f}s)"
        else:
            return False, f"FAILED: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT (>60s)"
    except FileNotFoundError:
        return False, "hermes command not found"
    except Exception as e:
        return False, f"ERROR: {str(e)}"


def main():
    print("Verifying Olympus profiles...\n")
    all_passed = True

    for profile in PROFILES:
        success, message = verify_profile(profile)
        status = "✓" if success else "✗"
        print(f"  {profile}: {status} {message}")
        if not success:
            all_passed = False

    print()
    if all_passed:
        print("All profiles verified successfully!")
        sys.exit(0)
    else:
        print("Some profiles failed verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write boot test**

```python
# tests/test_profile_boot.py
"""
Test that Hermes profiles boot and respond to basic prompts.

Note: These tests require Hermes Agent to be installed and configured.
They will be skipped if Hermes is not available.
"""
import subprocess
import pytest

PROFILES = [
    "zeus",
    "chronos",
    "iaso",
    "hermes-agent",
    "philia",
    "plutus",
    "hephaestus",
    "metis",
    "apollo",
    "midas",
]


def hermes_available() -> bool:
    try:
        subprocess.run(["hermes", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(
    not hermes_available(), reason="Hermes Agent not installed"
)


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_responds(profile):
    """Test that a profile boots and responds to a basic prompt."""
    result = subprocess.run(
        ["hermes", "-p", profile, "-z", "Who are you? Respond in one sentence."],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Profile {profile} failed: {result.stderr}"
    assert result.stdout.strip(), f"Profile {profile} returned empty response"
```

- [ ] **Step 3: Run verification**

```bash
python scripts/verify_profiles.py
```

Expected: All 10 profiles show OK with response times.

If Hermes is not yet installed or profiles are not configured, this will fail — that's expected. The script documents what success looks like.

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_profiles.py tests/test_profile_boot.py
git commit -m "feat: profile boot verification script and tests"
```

---

### Task 7: Phase 1 Decision Point — Hermes Capability Assessment

**Files:**
- Create: `docs/phase1-hermes-assessment.md`

- [ ] **Step 1: Write assessment document**

```markdown
# Phase 1: Hermes Capability Assessment

## Date: YYYY-MM-DD

## Question: Does Hermes Agent's gateway handle multi-profile management natively?

### Checklist

- [ ] Can Hermes manage multiple profiles from a single gateway process?
- [ ] Does Hermes have built-in health monitoring for profiles?
- [ ] Does Hermes support profile lifecycle management (start/stop/idle TTL)?
- [ ] Does Hermes have a scheduling system that can coordinate cross-profile cron jobs?
- [ ] Does Hermes expose a programmatic API for profile management?

### Findings

[Document findings here]

### Decision

- [ ] **Supervisor needed**: Hermes does not handle multi-profile management natively. Build Olympus Supervisor in Phase 2.
- [ ] **Supervisor not needed**: Hermes handles all lifecycle management. Drop Supervisor from the architecture.

### Rationale

[Explain the decision]
```

- [ ] **Step 2: Complete the assessment**

Based on Task 2 discovery findings, fill in the assessment document. Make the Supervisor decision.

- [ ] **Step 3: Commit**

```bash
git add docs/phase1-hermes-assessment.md
git commit -m "docs: Phase 1 Hermes capability assessment and Supervisor decision"
```

---

## Phase 1 Success Criteria Checklist

After completing all tasks, verify:

- [ ] All 10 profiles boot and respond to a basic prompt via Hermes' native interface without errors
- [ ] `share_knowledge` tool: write from one profile, read from another, verify round-trip against shared SQLite
- [ ] Hermes capability assessment completed with Supervisor decision documented

---

## Self-Review

### 1. Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Install Hermes Agent, create all 10 profiles | Task 2, Task 5 |
| Build custom tool plugins for domain integrations | Task 4 (share_knowledge) |
| Set up shared SQLite schema + share_knowledge tool | Task 3, Task 4 |
| Verify each profile boots independently | Task 6 |
| Decision point: Evaluate Hermes gateway capabilities | Task 7 |

**Note:** Domain tool plugins (home_assistant, withings_sync, gmail_triage, etc.) are NOT in Phase 1. They are listed in the spec as "build custom tool plugins" but the success criteria only require share_knowledge round-trip. Domain tools are Phase 2+ work. If the spec requires them in Phase 1, add tasks for each.

### 2. Placeholder Scan

- No TBD/TODO/fill-in-later patterns found
- All code steps have actual code
- All tests have actual test code
- Commands have expected output

### 3. Type Consistency

- `ShareKnowledgeTool` constructor uses `db_path: str | Path` and `allowed_scopes: list[str] | None`
- Tool `__call__` signature matches the spec's function signature
- SQLite schema uses TEXT for timestamps (SQLite doesn't have TIMESTAMPTZ)
- Profile configs use consistent model naming (qwen3.6-35b-a3b, qwen3.6-8b)

### Issues Found and Fixed

- Domain tool plugins (home_assistant, withings_sync, etc.) are NOT in Phase 1 scope — only share_knowledge is required. The spec says "Build custom tool plugins for domain integrations" but success criteria only require share_knowledge. If domain tools are needed in Phase 1, add them as separate tasks.
