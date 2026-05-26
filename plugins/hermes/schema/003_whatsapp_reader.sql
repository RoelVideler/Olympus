CREATE TABLE IF NOT EXISTS whatsapp_message_cache (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    chat_jid TEXT,
    sender TEXT,
    sender_display TEXT,
    original_text TEXT,
    sanitized_text TEXT,
    safety_score REAL,
    risk_category TEXT,
    threats TEXT,
    timestamp TEXT,
    is_from_me INTEGER DEFAULT 0,
    cached_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS whatsapp_chat_cache (
    jid TEXT PRIMARY KEY,
    name TEXT,
    is_group INTEGER DEFAULT 0,
    last_message_time TEXT,
    last_message TEXT,
    last_sender TEXT,
    cached_at TEXT DEFAULT (datetime('now'))
);
