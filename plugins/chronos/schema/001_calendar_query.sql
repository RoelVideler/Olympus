CREATE TABLE IF NOT EXISTS calendar_event_cache (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    calendar_id TEXT,
    summary TEXT,
    description TEXT,
    location TEXT,
    start_time TEXT,
    end_time TEXT,
    is_all_day INTEGER DEFAULT 0,
    status TEXT,
    attendees TEXT,
    cached_at TEXT DEFAULT (datetime('now'))
);
