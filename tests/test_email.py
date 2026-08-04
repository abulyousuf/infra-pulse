from unittest.mock import patch

from infra_pulse import alerts


def _email_config(enabled=True):
    return {
        "alerts": {
            "terminal": False,   # isolate email — no terminal noise
            "email": {
                "enabled": enabled,
                "smtp_host": "smtp.test",
                "smtp_port": 587,
                "username": "me@test",
                "password": "secret",
                "from_addr": "me@test",
                "to_addrs": ["you@test"],
            },
        }
    }


def test_email_sent_when_enabled():
    with patch("infra_pulse.alerts.smtplib.SMTP") as mock_smtp:
        # SMTP() is used as a context manager, so mock the __enter__ return
        server = mock_smtp.return_value.__enter__.return_value
        alerts.send_alert(_email_config(enabled=True), "GitHub", "up", "down", "HTTP 500")
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("me@test", "secret")
        server.sendmail.assert_called_once()


def test_email_not_sent_when_disabled():
    with patch("infra_pulse.alerts.smtplib.SMTP") as mock_smtp:
        alerts.send_alert(_email_config(enabled=False), "GitHub", "up", "down", "HTTP 500")
        mock_smtp.assert_not_called()


def test_email_failure_does_not_raise():
    """An SMTP failure must be swallowed — monitoring must not crash."""
    with patch("infra_pulse.alerts.smtplib.SMTP", side_effect=OSError("smtp down")):
        # Should not raise, despite the SMTP error
        alerts.send_alert(_email_config(enabled=True), "GitHub", "up", "down", "HTTP 500")