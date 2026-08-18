"""Command line entry: `dabt-proxy gate` and `dabt-proxy scaffold`."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import anyio

from .config import (
    ConfigError,
    add_common_arguments,
    add_gate_arguments,
    config_from_args,
    upstream_from_args,
)
from .scaffold import draft_manifest
from .server import serve
from .upstream import connect


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dabt-proxy",
        description=(
            "Gate an MCP server against Saudi regulatory policy. Which server is gated "
            "is decided by a tool manifest, so no vendor is built in."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gate = subparsers.add_parser(
        "gate", help="Run as a stdio MCP server that gates an upstream MCP server"
    )
    add_gate_arguments(gate)

    scaffold = subparsers.add_parser(
        "scaffold",
        help="Print a draft tool manifest built from an upstream server's tool list",
    )
    add_common_arguments(scaffold)
    return parser


async def run_scaffold(args: argparse.Namespace) -> int:
    """Read the upstream's tool list and print a manifest draft to stdout."""
    # Scaffolding deliberately loads no compliance map and no manifest: it exists
    # precisely for the case where no manifest yet exists.

    target = upstream_from_args(args)
    async with connect(target) as upstream:
        listed = await upstream.list_tools()
    tools = getattr(listed, "tools", ()) or ()
    print(draft_manifest(args.server_id, tools, target.describe()))
    print(
        f"# {len(tools)} tool(s) drafted. Review every line before use.",
        file=sys.stderr,
    )
    return 0


async def run_gate(args: argparse.Namespace) -> int:
    config = config_from_args(args)
    print(
        f"dabt-proxy: gating '{config.upstream.describe()}' as server_id "
        f"'{config.server_id}' (manifest {config.manifest.version}, policy map "
        f"{config.compliance_map.version}, "
        f"{'HTTP ' + config.policy_url if config.policy_url else 'in-process'} policy)",
        file=sys.stderr,
    )
    await serve(config)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = run_scaffold if args.command == "scaffold" else run_gate
    try:
        return anyio.run(handler, args)
    except ConfigError as error:
        # A misconfigured gate refuses to start rather than gating the wrong thing.
        print(f"dabt-proxy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
