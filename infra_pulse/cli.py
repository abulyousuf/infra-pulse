"""
cli.py — Command-line interface wiring using argparse.

Subcommands:
    add      Add a monitoring target
    list     List all configured targets
"""

import argparse
import sys

from . import db

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

    # list
    sub.add_parser("list", help="List all configured targets")

    return parser

# ---------- Command Handlers ----------

def cmd_add(args) -> None:
    # Validate tcp target format early for a friendly error
    if args.type == "tcp" and ":" not in args.target:
        print("TCP targets must be in 'host:port' form, e.g. example.com:443")
        sys.exit(1)

    if db.get_target(args.name) is not None:
        print(f"A target named '{args.name}' already exists.")
        sys.exit(1)

    db.add_target(args.name, args.type, args.target, args.interval)
    print(
        f"Added '{args.name}' "
        f"({args.type} → {args.target}) checking every {args.interval}s."
    )

def cmd_list(args) -> None:
    targets = db.list_targets()
    if not targets:
        print("No targets configured. Add one with 'add'.")
        return

    for t in targets:
        active = "yes" if t["active"] else "no"

        print(t["name"], t["type"], t["target"], f"{t['interval_seconds']}s", active)


HANDLERS = {
    "add": cmd_add,
    "list": cmd_list,
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