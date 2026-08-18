"""Drive the gate the way an agent would: over stdio, through real subprocesses.

    python demo/run_demo.py

This client spawns `dabt-proxy gate` as a subprocess, which spawns the fixture
PaaS server as a further subprocess. Nothing here is in-process, so what it
prints is what an MCP client actually receives from the gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SECRET_FRAGMENT = "s3cr3t"
IBAN = "SA0380000000608010167519"

CASES: list[tuple[str, str, dict[str, object]]] = [
    (
        "Provision a database outside the Kingdom",
        "create_database",
        {"region": "eu-west-1", "name": "customers"},
    ),
    (
        "Provision a database inside the Kingdom, then read back its credential",
        "create_database",
        {"region": "me-central-1", "name": "customers"},
    ),
    ("Read the application's environment variables", "list_env_vars", {"app_id": "app-1"}),
    ("Write a Saudi IBAN into a configuration value", "set_env_var", {"key": "PAYOUT", "value": IBAN}),
    ("Delete a database (regulatorily clean)", "delete_database", {"name": "staging"}),
]


def proxy_parameters() -> StdioServerParameters:
    upstream = f'"{sys.executable}" "{FIXTURES / "paas_stdio.py"}"'
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "dabt_proxy",
            "gate",
            "--server-id",
            "demo-paas",
            "--manifest",
            str(FIXTURES / "demo_paas.yaml"),
            "--upstream-stdio",
            upstream,
        ],
        cwd=str(ROOT),
    )


def show(title: str, tool: str, arguments: dict[str, object], result: object) -> None:
    print("=" * 78)
    print(f"AGENT: {title}")
    print(f"  calls {tool}({json.dumps(arguments, ensure_ascii=False)})")
    print("-" * 78)

    blocked = getattr(result, "is_error", False)
    body = "\n".join(getattr(block, "text", "") for block in getattr(result, "content", ()))
    structured = getattr(result, "structured_content", None)

    print("BLOCKED" if blocked else "RELEASED")
    print(body)
    if structured is not None:
        print(f"  structuredContent: {json.dumps(structured, ensure_ascii=False)}")

    combined = body + json.dumps(structured, ensure_ascii=False) if structured else body
    for label, needle in (("credential", SECRET_FRAGMENT), ("IBAN", IBAN)):
        if needle in combined:
            print(f"  !! the {label} reached the agent")
    print()


async def main() -> None:
    async with Client(stdio_client(proxy_parameters())) as client:
        listed = await client.list_tools()
        print(f"Gate advertises {len(listed.tools)} upstream tool(s): "
              f"{', '.join(tool.name for tool in listed.tools)}\n")

        for title, tool, arguments in CASES:
            result = await client.call_tool(tool, arguments)
            show(title, tool, arguments, result)


if __name__ == "__main__":
    anyio.run(main)
