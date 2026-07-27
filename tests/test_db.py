"""
test_db.py — Tests for the SQLite data layer.
"""

import sqlite3
import pytest

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

