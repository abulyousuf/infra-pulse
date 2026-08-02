"""
reports.py — Render uptime summaries and check history using rich tables.
"""

from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich import box

from . import db

console = Console()

def _status_style(status: str) -> str:
    """Map a status string to a rich colour markup."""
    return {
        "up":    "[green]● up[/green]",
        "down":  "[red]● down[/red]",
        "error": "[yellow]● error[/yellow]",
    }.get(status, f"[dim]{status}[/dim]")

def _uptime_style(pct) -> str:
    """Colour-code an uptime percentage."""
    if pct is None:
        return "[dim]n/a[/dim]"
    if pct >= 99:
        return f"[green]{pct}%[/green]"
    if pct >= 90:
        return f"[yellow]{pct}%[/yellow]"
    return f"[red]{pct}%[/red]"

def print_summary(hours: int = 24) -> None:
    """Print a one-row-per-target uptime summary table."""
    rows = db.get_all_uptime_stats(hours=hours)

    if not rows:
        console.print("[dim]No targets configured yet. Add one with 'add'.[/dim]")
        return

    table = Table(
        title=f"Infra Pulse — Uptime Summary (last {hours}h)",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Target", overflow="fold")
    table.add_column("Last Status")
    table.add_column("Uptime", justify="right")
    table.add_column("Avg ms", justify="right")
    table.add_column("Checks", justify="right")

    for r in rows:
        table.add_row(
            r["name"],
            r["type"],
            r["target"],
            _status_style(r["last_status"]),
            _uptime_style(r["uptime_pct"]),
            str(r["avg_response_ms"]) if r["avg_response_ms"] is not None else "[dim]n/a[/dim]",
            str(r["total"]),
        )

    console.print(table)

def print_target_history(name: str, limit: int = 20) -> None:
    """Print detailed recent check history for a single target."""
    target = db.get_target(name)
    if target is None:
        console.print(f"[red]No target named '{name}'.[/red]")
        return

    stats = db.get_uptime_stats(target["id"], hours=24)
    console.print(
        f"\n[bold]{name}[/bold]  ([cyan]{target['type']}[/cyan] → {target['target']})"
    )
    console.print(
        f"Last 24h: {_uptime_style(stats['uptime_pct'])} uptime "
        f"across {stats['total']} checks "
        f"({stats['up']} up / {stats['down']} down / {stats['error']} error)\n"
    )

    recent_checks = db.get_recent_checks(target["id"], limit=limit)
    if not recent_checks:
        console.print("[dim]No checks recorded yet.[/dim]")
        return

    table = Table(box=box.SIMPLE, header_style="bold cyan")
    table.add_column("Checked At (UTC)")
    table.add_column("Status")
    table.add_column("Response", justify="right")
    table.add_column("Detail", overflow="fold")

    for c in recent_checks:
        ts = _format_timestamp(c["checked_at"])
        ms = f"{c['response_time_ms']} ms" if c["response_time_ms"] is not None else "[dim]—[/dim]"
        table.add_row(ts, _status_style(c["status"]), ms, c["detail"] or "")

    console.print(table)

def _format_timestamp(iso_string: str) -> str:
    """Trim an ISO timestamp to second precision for display."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_string