"""
conftest.py — Shared pytest fixtures.

`fresh_db` points the db module at a throwaway SQLite file in a temp directory,
so tests never touch a real database and are fully isolated from each other.
"""


import pytest

from infra_pulse import db as db_module

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Return the db module wired to a temporary, empty database."""
    test_db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("INFRA_PULSE_DB", test_db_path)
    # db.DB_PATH is read at import time, so patch the module attribute too.
    monkeypatch.setattr(db_module, "DB_PATH", test_db_path)
    db_module.init_db()
    return db_module