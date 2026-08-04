"""
config.py — Loads configuration from config.json.

config.json holds email/SMTP settings and global defaults. It is git-ignored
because it contains credentials. See config.example.json for the template.
"""

import copy
import json
import os
from typing import Any

CONFIG_PATH = os.environ.get("INFRA_PULSE_CONFIG", "config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "default_interval_seconds": 60,
    "alerts": {
        "terminal": True,
        "log_file": "pulse.log",
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "from_addr": "",
            "to_addrs": [],
        },
    },
}

def load_config() -> dict:
    """
    Load config.json, falling back to defaults for any missing keys.

    If the file doesn't exist, return defaults so the tool still runs
    (with email disabled).
    """
    if not os.path.exists(CONFIG_PATH):
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to read {CONFIG_PATH}: {e}")

    return _deep_merge(DEFAULT_CONFIG, user_config)

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new independent dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result