"""Seed test data in SQLite for Dashboard integration testing.

Inserts sample health, wiki, calendar, contacts, and preferences records
into the shared Olympus database at ~/.hermes/olympus.db.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = os.path.expanduser("~/.hermes/olympus.db")


def get_connection() -> sqlite3.Connection:
    """Get or create a connection to the Olympus database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure all required tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS olympus_knowledge (
            rowid INTEGER PRIMARY KEY,
            id TEXT NOT NULL UNIQUE,
            scope TEXT NOT NULL CHECK(scope IN ('personal', 'business', 'global')),
            domain TEXT NOT NULL CHECK(length(domain) <= 100),
            fact TEXT NOT NULL CHECK(length(fact) <= 10000),
            confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
            source_profile TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS agent_profiles (
            name TEXT PRIMARY KEY,
            hermes_profile TEXT NOT NULL,
            run_mode TEXT NOT NULL DEFAULT 'on-demand' CHECK(run_mode IN ('always-on', 'on-demand', 'cron-only')),
            model_provider TEXT,
            model_name TEXT,
            status TEXT DEFAULT 'stopped' CHECK(status IN ('stopped', 'running', 'error'))
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            attendees TEXT,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            role TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)


def seed_profiles(conn: sqlite3.Connection) -> None:
    """Seed agent profile data."""
    profiles = [
        ("zeus", "zeus", "always-on", "openai", "gpt-4o", "running"),
        ("chronos", "chronos", "on-demand", "anthropic", "claude-sonnet-4-20250514", "stopped"),
        ("iaso", "iaso", "on-demand", "openai", "gpt-4o-mini", "stopped"),
        ("plutus", "plutus", "on-demand", "anthropic", "claude-sonnet-4-20250514", "stopped"),
        ("philia", "philia", "on-demand", "openai", "gpt-4o", "stopped"),
        ("hephaestus", "hephaestus", "on-demand", "anthropic", "claude-sonnet-4-20250514", "stopped"),
        ("metis", "metis", "always-on", "openai", "gpt-4o", "running"),
        ("apollo", "apollo", "cron-only", "anthropic", "claude-sonnet-4-20250514", "stopped"),
        ("midas", "midas", "cron-only", "openai", "gpt-4o", "stopped"),
        ("hermes-agent", "hermes-agent", "always-on", "openai", "gpt-4o-mini", "running"),
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO agent_profiles
           (name, hermes_profile, run_mode, model_provider, model_name, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        profiles,
    )


def seed_knowledge(conn: sqlite3.Connection) -> None:
    """Seed wiki/knowledge entries."""
    entries = [
        ("wiki-001", "personal", "health", "Daily step goal is 10,000 steps. Current streak: 14 days.", 1.0, "zeus"),
        ("wiki-002", "personal", "health", "Preferred workout time: 7:00 AM. Gym location: Equinox Downtown.", 1.0, "zeus"),
        ("wiki-003", "personal", "health", "Allergic to penicillin. Blood type: O+.", 1.0, "iaso"),
        ("wiki-004", "business", "finance", "Monthly revenue target: $50,000. Current MRR: $38,200.", 1.0, "plutus"),
        ("wiki-005", "business", "finance", "Primary bank: Chase Business. Account ends in 4821.", 0.9, "plutus"),
        ("wiki-006", "business", "project", "Q2 priority: Launch Olympus v2.0. Deadline: June 30.", 1.0, "metis"),
        ("wiki-007", "global", "system", "Hermes Agent version: 0.14.0. Plugin API is stable.", 1.0, "hermes-agent"),
        ("wiki-008", "global", "system", "Database path: ~/.hermes/olympus.db. Backup daily.", 1.0, "hermes-agent"),
        ("wiki-009", "personal", "preference", "Coffee order: oat milk flat white, 1 pump vanilla.", 1.0, "zeus"),
        ("wiki-010", "personal", "preference", "Timezone: Europe/Amsterdam (CET/CEST).", 1.0, "zeus"),
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO olympus_knowledge
           (id, scope, domain, fact, confidence, source_profile)
           VALUES (?, ?, ?, ?, ?, ?)""",
        entries,
    )


def seed_calendar(conn: sqlite3.Connection) -> None:
    """Seed calendar events."""
    now = datetime.now()
    events = [
        ("cal-001", "Team standup", "Daily sync with the team", (now + timedelta(hours=2)).isoformat(), (now + timedelta(hours=2, minutes=30)).isoformat(), "Zoom", '["alice", "bob"]', "google"),
        ("cal-002", "Gym session", "Leg day", (now + timedelta(hours=5)).isoformat(), (now + timedelta(hours=6, minutes=30)).isoformat(), "Equinox Downtown", None, "manual"),
        ("cal-003", "Client demo", "Show Olympus dashboard to Acme Corp", (now + timedelta(days=1, hours=10)).isoformat(), (now + timedelta(days=1, hours=11)).isoformat(), "Google Meet", '["client@acme.com"]', "google"),
        ("cal-004", "Dentist appointment", "Regular checkup", (now + timedelta(days=3, hours=14)).isoformat(), (now + timedelta(days=3, hours=15)).isoformat(), "Dr. Smith's Office", None, "manual"),
        ("cal-005", "Sprint planning", "Q2 sprint 3 planning", (now + timedelta(days=4, hours=9)).isoformat(), (now + timedelta(days=4, hours=10, minutes=30)).isoformat(), "Office", '["team"]', "google"),
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO calendar_events
           (id, title, description, start_time, end_time, location, attendees, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        events,
    )


def seed_contacts(conn: sqlite3.Connection) -> None:
    """Seed contacts."""
    contacts = [
        ("contact-001", "Alice Johnson", "alice@example.com", "+31-6-1234-5678", "Acme Corp", "CTO", "Key decision maker"),
        ("contact-002", "Bob Smith", "bob@example.com", "+31-6-8765-4321", "Acme Corp", "Engineering Lead", "Technical contact"),
        ("contact-003", "Dr. Smith", "dr.smith@clinic.nl", "+31-20-123-4567", "Amsterdam Dental", "Dentist", "Next appointment in 3 days"),
        ("contact-004", "Carlos Rivera", "carlos@startup.io", "+1-555-0123", "StartupIO", "Founder", "Met at conference"),
        ("contact-005", "Diana Chen", "diana@design.co", "+31-6-5555-1234", "DesignCo", "UX Designer", "Freelance collaborator"),
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO contacts
           (id, name, email, phone, company, role, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        contacts,
    )


def seed_preferences(conn: sqlite3.Connection) -> None:
    """Seed user preferences."""
    prefs = [
        ("theme", "dark"),
        ("language", "en"),
        ("timezone", "Europe/Amsterdam"),
        ("date_format", "DD/MM/YYYY"),
        ("time_format", "24h"),
        ("notifications_enabled", "true"),
        ("dashboard_port", "8080"),
        ("default_profile", "zeus"),
        ("calendar_source", "google"),
        ("units_system", "metric"),
    ]

    conn.executemany(
        "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
        prefs,
    )


def seed_all() -> None:
    """Run all seed functions."""
    conn = get_connection()
    try:
        ensure_schema(conn)
        seed_profiles(conn)
        seed_knowledge(conn)
        seed_calendar(conn)
        seed_contacts(conn)
        seed_preferences(conn)
        conn.commit()
        print(f"Seed data written to {DB_PATH}")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_all()
