CREATE TABLE IF NOT EXISTS gmail_triage_cache (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    thread_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT,
    snippet TEXT,
    received_at TEXT,
    labels TEXT,
    is_important INTEGER DEFAULT 0,
    triage_score REAL,
    triage_category TEXT,
    processed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gmail_sent_log (
    id TEXT PRIMARY KEY,
    to_recipients TEXT NOT NULL,
    cc_recipients TEXT,
    subject TEXT,
    sent_at TEXT DEFAULT (datetime('now')),
    thread_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gmail_sync_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
