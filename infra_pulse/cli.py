"""
cli.py — Command-line interface wiring using argparse.

Subcommands:
    list     List all configured targets
"""

import argparse
import sys

from . import db

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infra-pulse",
        description="Infra Pulse — a CLI uptime monitor for URLs, hosts, ports, and DNS."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all configured targets")

    return parser

# ---------- Command Handlers ----------

def cmd_list(args) -> None:
    targets = db.list_targets()
    if not targets:
        print("No targets configured. Add one with 'add'.")
        return

    for t in targets:
        active = "yes" if t["active"] else "no"

        print(t["name"], t["type"], t["target"], f"{t['interval_seconds']}s", active)


HANDLERS = {
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