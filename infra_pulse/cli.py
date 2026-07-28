"""
cli.py — Command-line interface wiring using argparse.

Subcommands:
    add      Add a monitoring target
    remove   Remove a target by name
    list     List all configured targets
    check    Run a single one-off check and print the result
"""

import argparse
import sys

from rich.console import Console
from rich.table import Table
from rich import box

from . import db, checks

console = Console()

VALID_TYPES = ("http", "ping", "tcp", "dns")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infra-pulse",
        description="Infra Pulse — a CLI uptime monitor for URLs, hosts, ports, and DNS."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a monitoring target")
    p_add.add_argument("--name", required=True, help="Unique name for the target")
    p_add.add_argument("--type", required=True, choices=VALID_TYPES, help="Check type")
    p_add.add_argument("--target", required=True, help="What to check: URL (http), host/IP (ping/dns), or host:port (tcp)")
    p_add.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60)")

    # remove
    p_rm = sub.add_parser("remove", help="Remove a target by name")
    p_rm.add_argument("--name", required=True, help="Name of the target to remove")

    # list
    sub.add_parser("list", help="List all configured targets")

    # check (one-off)
    p_check = sub.add_parser("check", help="Run a single check now and print the result")
    p_check.add_argument("--name", required=True)

    return parser

# ---------- Command Handlers ----------

def cmd_add(args) -> None:
    # Validate tcp target format early for a friendly error
    if args.type == "tcp" and ":" not in args.target:
        console.print("[red]TCP targets must be in 'host:port' form, e.g. example.com:443[/red]")
        sys.exit(1)

    if db.get_target(args.name) is not None:
        console.print(f"[red]A target named '{args.name}' already exists.[/red]")
        sys.exit(1)

    db.add_target(args.name, args.type, args.target, args.interval)
    console.print(
        f"[green]Added[/green] '{args.name}' "
        f"([cyan]{args.type}[/cyan] → {args.target}) checking every {args.interval}s."
    )

def cmd_remove(args) -> None:
    if db.remove_target(args.name):
        console.print(f"[green]Removed[/green] '{args.name}'.")
    else:
        console.print(f"[red]No target named '{args.name}'.[/red]")
        sys.exit(1)

def cmd_list(args) -> None:
    targets = db.list_targets()
    if not targets:
        console.print("[dim]No targets configured. Add one with 'add'.[/dim]")
        return

    table = Table(title="Configured Targets", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Target", overflow="fold")
    table.add_column("Interval", justify="right")
    table.add_column("Active")

    for t in targets:
        active = "[green]yes[/green]" if t["active"] else "[dim]no[/dim]"
        table.add_row(t["name"], t["type"], t["target"], f"{t['interval_seconds']}s", active)

    console.print(table)

def cmd_check(args) -> None:
    target = db.get_target(args.name)
    if target is None:
        console.print(f"[red]No target named '{args.name}'.[/red]")
        sys.exit(1)

    console.print(f"Checking [bold]{args.name}[/bold] ([cyan]{target['type']}[/cyan] → {target['target']}) ...")
    result = checks.run_check(target["type"], target["target"])

    db.save_check(
        target_id=target["id"],
        status=result["status"],
        response_time_ms=result["response_time_ms"],
        detail=result["detail"],
    )

    colour = {"up": "green", "down": "red", "error": "yellow"}.get(result["status"], "white")
    ms = f"{result['response_time_ms']} ms" if result["response_time_ms"] is not None else "n/a"
    console.print(
        f"[{colour}]{result['status'].upper()}[/{colour}] "
        f"({ms}) — {result['detail']}"
    )

HANDLERS = {
    "add": cmd_add,
    "remove": cmd_remove,
    "list": cmd_list,
    "check": cmd_check,
}

def main(argv=None) -> None:
    """Entry point: parse args, ensure DB exists, dispatch."""
    db.init_db()

    parser = build_parser()
    args = parser.parse_args(argv)

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)