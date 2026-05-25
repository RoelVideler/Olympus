-- plugins/hephaestus/schema/001_home_maintenance.sql
-- Hephaestus home maintenance tracking schema (SQLite)

CREATE TABLE IF NOT EXISTS home_maintenance (
    id TEXT PRIMARY KEY,
    device TEXT NOT NULL,
    domain TEXT NOT NULL,
    action TEXT NOT NULL,
    notes TEXT DEFAULT '',
    scheduled_date TEXT,
    completed_date TEXT,
    recurrence_days INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
