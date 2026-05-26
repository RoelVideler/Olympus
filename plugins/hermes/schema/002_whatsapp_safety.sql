CREATE TABLE IF NOT EXISTS whatsapp_safety_log (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    chat_jid TEXT,
    sender TEXT,
    message_preview TEXT,
    safety_score REAL,
    risk_category TEXT,
    threats_detected TEXT,
    is_blocked INTEGER DEFAULT 0,
    scanned_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS whatsapp_safe_senders (
    id TEXT PRIMARY KEY,
    sender TEXT UNIQUE,
    display_name TEXT,
    trust_level REAL DEFAULT 1.0,
    verified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
