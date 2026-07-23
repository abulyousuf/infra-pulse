"""
db.py — SQLite database layer for Infra Pulse.

Handles all schema creation, target CRUD, and check result storage/querying.
"""

import os
import sqlite3
from datetime import datetime, timezone
from contextlib import closing

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
    with closing(get_connection()) as conn:
        with conn:
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

# ---------- Targets ----------

def add_target(name: str, check_type: str, target: str, interval: int = 60) -> int:
    """Insert a new monitoring target. Returns the new row id."""
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO targets (name, type, target, interval_seconds, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (name, check_type, target, interval, datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid

def remove_target(name: str) -> bool:
    """Delete a target by name. Returns True if a row was deleted."""
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute("DELETE FROM targets WHERE name = ?", (name,))
            return cur.rowcount > 0


def get_target(name: str) -> sqlite3.Row | None:
    """Fetch a single target by name, or None if not found."""
    with closing(get_connection()) as conn:
        with conn:
            return conn.execute(
                "SELECT * FROM targets WHERE name = ?", (name,)
            ).fetchone()


def list_targets(active_only: bool = False) -> list[sqlite3.Row]:
    """Return all targets, optionally filtered to active ones only."""
    with closing(get_connection()) as conn:
        with conn:
            query = "SELECT * FROM targets"
            if active_only:
                query += " WHERE active = 1"
            query += " ORDER BY name"
            return conn.execute(query).fetchall()