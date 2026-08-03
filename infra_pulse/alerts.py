"""
alerts.py — Alerting for state changes (up → down, down → up).

Supports channels:
  - terminal + log file (on by default)
  - email (optional, configured in config.json)

Alerts only fire on *state transitions* to avoid spamming on every check.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

from rich.console import Console

console = Console()

# Module-level logger configured by setup_logging()
logger = logging.getLogger("infra_pulse")

def setup_logging(log_file: str = "pulse.log") -> None:
    """Configure the file logger for alert records."""
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called more than once
    if logger.handlers:
        return

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

def send_alert(config: dict, target_name: str, old_status: str, new_status: str, detail: str) -> None:
    """
    Dispatch alerts across all enabled channels for a status transition.

    Args:
        config:      Loaded config dict (from config.load_config()).
        target_name: Name of the target that changed state.
        old_status:  Previous status ('up'/'down'/'error'/'unknown').
        new_status:  New status.
        detail:      Human-readable detail from the check.
    """
    alert_cfg = config.get("alerts", {})

    is_recovery = new_status == "up"
    symbol = "✅ RECOVERED" if is_recovery else "🔴 DOWN"
    message = (
        f"{symbol}: '{target_name}' changed {old_status} → {new_status}. {detail}"
    )

    if alert_cfg.get("terminal", True):
        logger.warning(message)
        colour = "green" if is_recovery else "red"
        console.print(f"[{colour}]{message}[/{colour}]")

    email_cfg = alert_cfg.get("email", {})
    if email_cfg.get("enabled", False):
        try:
            _send_email(email_cfg, target_name, new_status, message)
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

def _send_email(email_cfg: dict, target_name: str, new_status: str, body: str) -> None:
    """Send a single email alert via SMTP using STARTTLS."""
    subject = f"[Infra Pulse] {target_name} is {new_status.upper()}"
    full_body = (
        f"{body}\n\n"
        f"Time (UTC): {datetime.now(timezone.utc).isoformat()}\n"
        f"-- Infra Pulse"
    )

    msg = MIMEText(full_body)
    msg["Subject"] = subject
    msg["From"]    = email_cfg["from_addr"]
    msg["To"]      = ", ".join(email_cfg["to_addrs"])

    with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"], timeout=15) as server:
        server.starttls()
        server.login(email_cfg["username"], email_cfg["password"])
        server.sendmail(
            email_cfg["from_addr"],
            email_cfg["to_addrs"],
            msg.as_string(),
        )

    logger.info(f"Email alert sent for '{target_name}' to {email_cfg['to_addrs']}")