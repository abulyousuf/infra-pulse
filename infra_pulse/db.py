"""
db.py — SQLite database layer for Infra Pulse.

Handles all schema creation, target CRUD, and check result storage/querying.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
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

# ---------- Check Results ----------

def save_check(target_id: int, status: str, response_time_ms: float | None, detail: str = "") -> None:
    """Persist a single check result."""
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO checks (target_id, checked_at, status, response_time_ms, detail)
                VALUES (?, ?, ?, ?, ?)
                """,
                (target_id, datetime.now(timezone.utc).isoformat(), status, response_time_ms, detail),
            )

def get_uptime_stats(target_id: int, hours: int = 24) -> dict:
    """
    Calculate uptime % and average response time over the last N hours.

    Returns a dict with keys: total, up, down, error, uptime_pct, avg_response_ms.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with closing(get_connection()) as conn:
        with conn:
            rows = conn.execute(
                """
                SELECT status, response_time_ms
                FROM checks
                WHERE target_id = ?
                AND checked_at >= ?
                """,
                (target_id, cutoff),
            ).fetchall()

    total = len(rows)
    if total == 0:
        return {"total": 0, "up": 0, "down": 0, "error": 0, "uptime_pct": None, "avg_response_ms": None}

    up    = sum(1 for r in rows if r["status"] == "up")
    down  = sum(1 for r in rows if r["status"] == "down")
    error = sum(1 for r in rows if r["status"] == "error")

    response_times = [r["response_time_ms"] for r in rows if r["response_time_ms"] is not None]
    avg_ms = round(sum(response_times) / len(response_times), 2) if response_times else None

    return {
        "total":          total,
        "up":             up,
        "down":           down,
        "error":          error,
        "uptime_pct":     round((up / total) * 100, 2),
        "avg_response_ms": avg_ms,
    }

def get_recent_checks(target_id: int, limit: int = 20) -> list[sqlite3.Row]:
    """Return the most recent N checks for a target, newest first."""
    with closing(get_connection()) as conn:
        with conn:
            return conn.execute(
                """
                SELECT * FROM checks
                WHERE target_id = ?
                ORDER BY checked_at DESC
                LIMIT ?
                """,
                (target_id, limit),
            ).fetchall()

def get_last_check(target_id: int) -> sqlite3.Row | None:
    """Return the most recent check for a target, or None if never checked."""
    with closing(get_connection()) as conn:
        with conn:
            return conn.execute(
                """
                SELECT * FROM checks
                WHERE target_id = ?
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                (target_id,),
            ).fetchone()

def get_all_uptime_stats(hours: int = 24) -> list[dict]:
    """Return uptime stats for every target, merged with target metadata."""
    targets = list_targets()
    results = []
    for t in targets:
        stats = get_uptime_stats(t["id"], hours=hours)
        last  = get_last_check(t["id"])
        results.append({
            "name":            t["name"],
            "type":            t["type"],
            "target":          t["target"],
            "active":          bool(t["active"]),
            "last_status":     last["status"] if last else "never checked",
            "last_checked":    last["checked_at"] if last else None,
            **stats,
        })
    return results