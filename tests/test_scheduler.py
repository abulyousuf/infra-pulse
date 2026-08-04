"""
test_scheduler.py — Tests for the scheduler's per-check transition logic.
"""
from unittest.mock import patch
from infra_pulse import scheduler

def _fake_target(fresh_db):
    tid = fresh_db.add_target("T", "http", "https://x.com")
    return fresh_db.get_target("T")

def _run_checks(fresh_db, statuses, seed_status="unknown"):
    """Run _check_and_record for each status against one target; return alert calls."""
    target = _fake_target(fresh_db)
    state = {"next_due": 0.0, "last_status": seed_status}
    alert_calls = []
    cfg = {"alerts": {"terminal": False, "log_file": "pulse.log"}}
    with patch("infra_pulse.scheduler.alerts.send_alert",
               side_effect=lambda **kw: alert_calls.append((kw["old_status"], kw["new_status"]))):
        for s in statuses:
            with patch("infra_pulse.scheduler.checks.run_check",
                       return_value={"status": s, "response_time_ms": 10.0, "detail": "x"}):
                scheduler._check_and_record(cfg, target, state)
    return alert_calls, state

def test_no_alert_on_steady_up(fresh_db):
    calls, _ = _run_checks(fresh_db, ["up", "up"], seed_status="up")
    assert calls == []

def test_alert_on_down_and_recovery(fresh_db):
    calls, _ = _run_checks(fresh_db, ["down", "up"], seed_status="up")
    assert calls == [("up", "down"), ("down", "up")]

def test_state_last_status_updates(fresh_db):
    _, state = _run_checks(fresh_db, ["down"], seed_status="up")
    assert state["last_status"] == "down"