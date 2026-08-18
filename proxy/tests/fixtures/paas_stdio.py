"""Run the fixture PaaS server as a real stdio MCP server.

Used as the upstream when the demo exercises the proxy through actual pipes and
subprocesses rather than in-process transports.
"""

from __future__ import annotations

import anyio
from mcp import stdio_server
from paas_server import build_server


async def main() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
