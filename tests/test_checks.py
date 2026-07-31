"""
test_checks.py — Tests for the check logic.

Techniques demonstrated:
  - Mocking network calls with unittest.mock so tests run offline and instantly.
  - Testing pure logic (the run_check dispatcher's input validation).
"""

from unittest.mock import patch, MagicMock
from infra_pulse import checks
import requests

# ----------HTTP: status-code decision rules (network mocked) ----------

def _fake_response(status_code: int) -> MagicMock:
    fake = MagicMock()
    fake.status_code = status_code
    return fake

def test_http_up_on_200():
    with patch("infra_pulse.checks.requests.get", return_value=_fake_response(200)):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "up"
    assert "200" in result["detail"]

def test_http_down_on_404():
    with patch("infra_pulse.checks.requests.get", return_value=_fake_response(404)):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "down"

def test_http_down_on_500():
    with patch("infra_pulse.checks.requests.get", return_value=_fake_response(500)):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "down"

def test_http_down_on_connection_error():
    with patch("infra_pulse.checks.requests.get",
               side_effect=requests.exceptions.ConnectionError("refused")):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "down"

def test_http_up_on_301_redirect_class():
    with patch("infra_pulse.checks.requests.get", return_value=_fake_response(301)):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "up"

def test_http_down_on_timeout():
    with patch(
        "infra_pulse.checks.requests.get",
        side_effect=requests.exceptions.Timeout(),
    ):
        result = checks.check_http("https://whatever.test")
    assert result["status"] == "down"
    assert "imed out" in result["detail"]  # matches "Timed out"

def test_http_result_shape_is_consistent():
    """Every check must return the same three keys — the contract the app relies on."""
    with patch("infra_pulse.checks.requests.get", return_value=_fake_response(200)):
        result = checks.check_http("https://whatever.test")
    assert set(result.keys()) == {"status", "response_time_ms", "detail"}

# ---------- Dispatcher: input validation (pure logic, no network) ---------

def test_tcp_target_without_port_is_error():
    result = checks.run_check("tcp", "example.com")
    assert result["status"] == "error"
    assert "host:port" in result["detail"]


def test_tcp_target_with_bad_port_is_error():
    result = checks.run_check("tcp", "example.com:notaport")
    assert result["status"] == "error"


def test_unknown_check_type_is_error():
    result = checks.run_check("carrier-pigeon", "example.com")
    assert result["status"] == "error"

# ---------- Ping RTT parsing (pure function) ----------

def test_parse_ping_rtt_linux_format():
    output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.3 ms"
    assert checks._parse_ping_rtt(output) == 12.3

def test_parse_ping_rtt_returns_none_when_absent():
    assert checks._parse_ping_rtt("Request timed out.") is None