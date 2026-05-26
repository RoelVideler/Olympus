-- plugins/iaso/schema/001_withings_sync.sql
-- Iaso Withings health sync schema (SQLite)

CREATE TABLE IF NOT EXISTS withings_vitals (
    id TEXT PRIMARY KEY,
    userid TEXT NOT NULL,
    vitals_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT DEFAULT '',
    measured_at TEXT NOT NULL,
    synced_at TEXT DEFAULT (datetime('now')),
    UNIQUE(userid, vitals_type, measured_at)
);

CREATE TABLE IF NOT EXISTS withings_sleep (
    id TEXT PRIMARY KEY,
    userid TEXT NOT NULL,
    date TEXT NOT NULL,
    sleep_score INTEGER,
    total_sleep_seconds INTEGER,
    rem_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    awake_seconds INTEGER,
    hr_average REAL,
    hr_min REAL,
    hr_max REAL,
    spo2_average REAL,
    snoring_seconds INTEGER,
    synced_at TEXT DEFAULT (datetime('now')),
    UNIQUE(userid, date)
);

CREATE TABLE IF NOT EXISTS withings_activity (
    id TEXT PRIMARY KEY,
    userid TEXT NOT NULL,
    date TEXT NOT NULL,
    steps INTEGER,
    distance REAL,
    elevation REAL,
    calories REAL,
    total_calories REAL,
    hr_average REAL,
    hr_min REAL,
    hr_max REAL,
    active_seconds INTEGER,
    synced_at TEXT DEFAULT (datetime('now')),
    UNIQUE(userid, date)
);
