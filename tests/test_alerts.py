"""
test_alerts.py — Tests for transition-based alerting.
"""
import argparse
from unittest.mock import patch

from infra_pulse import cli


def _run_sequence(fresh_db, statuses):
    """Run cmd_check for each status, return list of (old, new) passed to send_alert."""
    fresh_db.add_target("T", "http", "https://x.com")
    args = argparse.Namespace(name="T")
    alert_calls = []
    with patch("infra_pulse.cli.alerts.send_alert",
               side_effect=lambda cfg, name, old, new, detail: alert_calls.append((old, new))):
        for s in statuses:
            with patch("infra_pulse.checks.run_check",
                       return_value={"status": s, "response_time_ms": 10.0, "detail": "x"}):
                cli.cmd_check(args)
    return alert_calls


def test_no_alert_on_steady_up(fresh_db):
    calls = _run_sequence(fresh_db, ["up", "up", "up"])
    assert calls == []   # never transitioned, never alerted

def test_alert_on_down_then_recovery(fresh_db):
    calls = _run_sequence(fresh_db, ["up", "down", "up"])
    assert calls == [("up", "down"), ("down", "up")]   # exactly two transitions

def test_first_check_down_alerts(fresh_db):
    calls = _run_sequence(fresh_db, ["down"])
    assert calls == [("unknown", "down")]   # started broken → alert

def test_first_check_up_is_silent(fresh_db):
    calls = _run_sequence(fresh_db, ["up"])
    assert calls == []   # started healthy → no alert