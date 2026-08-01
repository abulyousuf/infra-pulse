"""
test_db.py — Tests for the SQLite data layer (targets CRUD + uptime stats).

Technique demonstrated: isolating the database with a temp file per test
(see conftest.py's fresh_db fixture).
"""

import sqlite3
import pytest

from contextlib import closing

# ---------- Target CRUD ----------

def test_add_then_get_target(fresh_db):
    fresh_db.add_target("API", "http", "https://example.com", 30)
    row = fresh_db.get_target("API")
    assert row is not None
    assert row["type"] == "http"
    assert row["target"] == "https://example.com"
    assert row["interval_seconds"] == 30
    assert row["active"] == 1

def test_get_missing_target_returns_none(fresh_db):
    assert fresh_db.get_target("nope") is None

def test_list_targets_sorted_by_name(fresh_db):
    fresh_db.add_target("Zeta", "dns", "z.com")
    fresh_db.add_target("Alpha", "dns", "a.com")
    names = [t["name"] for t in fresh_db.list_targets()]
    assert names == ["Alpha", "Zeta"]

def test_remove_target_returns_true_then_false(fresh_db):
    fresh_db.add_target("X", "http", "https://x.com")
    assert fresh_db.remove_target("X") is True
    assert fresh_db.remove_target("X") is False

def test_remove_missing_target_returns_false(fresh_db):
    assert fresh_db.remove_target("ghost") is False

def test_duplicate_name_raises(fresh_db):
    fresh_db.add_target("X", "http", "https://x.com")
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.add_target("X", "ping", "1.2.3.4")

def test_invalid_type_raises(fresh_db):
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.add_target("X", "carrier-pigeon", "somewhere")

def test_deleting_target_cascades_to_checks(fresh_db):
    tid = fresh_db.add_target("X", "http", "https://x.com")
    fresh_db.save_check(tid, "up", 50.0, "HTTP 200")

    # confirm the check exists
    with closing(fresh_db.get_connection()) as conn:
        with conn:
            before = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    assert before == 1

    fresh_db.remove_target("X")

    # confirm cascade removed it
    with closing(fresh_db.get_connection()) as conn:
        with conn:
            after = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    assert after == 0

# ---------- Uptime Stats ----------

def test_uptime_50_percent_mixed(fresh_db):
    tid = fresh_db.add_target("X", "http", "https://x.com")
    fresh_db.save_check(tid, "up", 50.0, "HTTP 200")
    fresh_db.save_check(tid, "down", 80.0, "HTTP 500")
    stats = fresh_db.get_uptime_stats(tid)
    assert stats["uptime_pct"] == 50.0
    assert stats["up"] == 1
    assert stats["down"] == 1

def test_uptime_none_when_no_checks(fresh_db):
    """The zero-checks edge case must not divide by zero."""
    tid = fresh_db.add_target("X", "http", "https://x.com")
    stats = fresh_db.get_uptime_stats(tid)
    assert stats["total"] == 0
    assert stats["uptime_pct"] is None
    assert stats["avg_response_ms"] is None