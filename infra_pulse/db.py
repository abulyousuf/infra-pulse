"""
db.py — SQLite database layer for Infra Pulse.

Handles all schema creation, target CRUD, and check result storage/querying.
"""

import sqlite3
import os

DB_PATH = os.environ.get("INFRA_PULSE_DB", "infra_pulse.db")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS targets (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL UNIQUE,
                type             TEXT    NOT NULL CHECK(type IN ('http','ping','tcp','dns')),
                target           TEXT    NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 60,
                active           INTEGER NOT NULL DEFAULT 1,
                created_at       TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS checks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id        INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
                checked_at       TEXT    NOT NULL,
                status           TEXT    NOT NULL CHECK(status IN ('up','down','error')),
                response_time_ms REAL,
                detail           TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_checks_target_id   ON checks(target_id);
            CREATE INDEX IF NOT EXISTS idx_checks_checked_at  ON checks(checked_at);
        """)