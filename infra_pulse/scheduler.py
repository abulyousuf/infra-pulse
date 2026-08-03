"""
scheduler.py — The monitoring loop.

Runs forever, checking each active target at its own configured interval,
storing every result, and firing alerts on status transitions.
"""

import time
from datetime import datetime, timezone

from rich.console import Console

from . import db, checks, alerts

console = Console()

def _now() -> float:
    return time.monotonic()

def run_loop(config: dict, poll_resolution: int = 1) -> None:
    """
    Start the monitoring loop.

    Each target is checked every `interval_seconds`. We track the last-check
    time per target and the last-known status to detect transitions.

    Args:
        config:          Loaded config dict.
        poll_resolution: How often (seconds) the loop wakes to see what's due.
    """
    alerts.setup_logging(config.get("alerts", {}).get("log_file", "pulse.log"))

    # Per-target bookkeeping: { target_id: {"next_due": float, "last_status": str} }
    state: dict[int, dict] = {}

    console.print("[bold green]Infra Pulse monitoring started.[/bold green] Press Ctrl+C to stop.\n")

    try:
        while True:
            targets = db.list_targets(active_only=True)

            if not targets:
                console.print("[dim]No active targets. Add one with 'add', then restart.[/dim]")
                time.sleep(5)
                continue

            now = _now()

            for t in targets:
                tid = t["id"]

                # Seed bookkeeping for newly-seen targets (check immediately)
                if tid not in state:
                    last = db.get_last_check(tid)
                    state[tid] = {
                        "next_due":    now,
                        "last_status": last["status"] if last else "unknown",
                    }

                if now >= state[tid]["next_due"]:
                    _check_and_record(config, t, state[tid])
                    state[tid]["next_due"] = now + t["interval_seconds"]

            # Drop bookkeeping for targets that were removed/deactivated
            active_ids = {t["id"] for t in targets}
            for stale_id in list(state.keys()):
                if stale_id not in active_ids:
                    del state[stale_id]

            time.sleep(poll_resolution)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Monitoring stopped.[/bold yellow]")

def _check_and_record(config: dict, target, target_state: dict) -> None:
    """Run one check for a target, store it, and alert on transitions."""
    result = checks.run_check(target["type"], target["target"])

    db.save_check(
        target_id=target["id"],
        status=result["status"],
        response_time_ms=result["response_time_ms"],
        detail=result["detail"],
    )

    new_status = result["status"]
    old_status = target_state["last_status"]

    # Live feedback line
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    colour = {"up": "green", "down": "red", "error": "yellow"}.get(new_status, "white")
    console.print(
        f"[dim]{ts}[/dim] [{colour}]{new_status.upper():5}[/{colour}] "
        f"{target['name']} — {result['detail']}"
    )

    # Alert only on a real transition (and not on the very first 'unknown' seed
    # unless it goes straight to down/error)
    transitioned = old_status != new_status
    seeded_down  = old_status == "unknown" and new_status != "up"

    if transitioned and (old_status != "unknown" or seeded_down):
        alerts.send_alert(
            config=config,
            target_name=target["name"],
            old_status=old_status,
            new_status=new_status,
            detail=result["detail"],
        )

    target_state["last_status"] = new_status