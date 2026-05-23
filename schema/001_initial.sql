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
