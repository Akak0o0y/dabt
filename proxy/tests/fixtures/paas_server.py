"""A small PaaS-shaped MCP server, used by the tests and the demo.

This exists so the gate can be exercised end to end against a server whose tool
schema is actually known. The packaged `cranl.yaml` is a reconstruction with
every entry `needs_verification`, so every call against it resolves to REVIEW -
correct, and safe, but it cannot demonstrate the release, redaction, or
credential-withholding paths.

Because this server is defined here, its manifest can honestly say `verified`:
the claim "this tool returns a connection string" is checkable by reading the
code immediately below it, which is the standard the manifest format asks for.
"""

from __future__ import annotations

from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

SERVER_ID = "demo-paas"

# What the fixture "stores", so a read can return something worth gating.
ENV_VARS: dict[str, str] = {
    "PORT": "8080",
    "LOG_LEVEL": "info",
    "SUPPORT_CONTACT": "0512345678",
    "BILLING_IBAN": "SA0380000000608010167519",
}

TOOLS: list[types.Tool] = [
    types.Tool(
        name="create_database",
        description="Provision a database in a region and return its connection string.",
        inputSchema={
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "name": {"type": "string"},
                "replicas": {"type": "integer"},
            },
            "required": ["region", "name"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "connection_string": {"type": "string"},
                "id": {"type": "string"},
            },
        },
    ),
    types.Tool(
        name="list_env_vars",
        description="List configured environment variables for the application.",
        inputSchema={"type": "object", "properties": {"app_id": {"type": "string"}}},
        outputSchema={
            "type": "object",
            "properties": {"variables": {"type": "array", "items": {"type": "string"}}},
        },
    ),
    types.Tool(
        name="set_env_var",
        description="Set one environment variable.",
        inputSchema={
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"],
        },
        outputSchema={"type": "object", "properties": {"status": {"type": "string"}}},
    ),
    types.Tool(
        name="delete_database",
        description="Delete a database by name. Carries no personal data.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        outputSchema={"type": "object", "properties": {"status": {"type": "string"}}},
    ),
]


class Recorder:
    """Records what actually reached the server, which is what the tests assert on."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def called_tools(self) -> list[str]:
        return [name for name, _ in self.calls]


def _result(structured: dict[str, Any], text: str | None = None) -> types.CallToolResult:
    """Return structured content mirrored as text, exactly as real servers do.

    The mirroring is not incidental: it is the condition under which a proxy that
    redacts only `structuredContent` leaks the original through `content`.
    """
    import json

    body = text if text is not None else json.dumps(structured, ensure_ascii=False)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=body)],
        structuredContent=structured,
        isError=False,
    )


def build_server(recorder: Recorder | None = None) -> Server[Any]:
    recorder = recorder if recorder is not None else Recorder()

    async def on_list_tools(_: Any, __: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=TOOLS)

    async def on_call_tool(_: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        arguments = dict(params.arguments or {})
        recorder.calls.append((params.name, arguments))

        if params.name == "create_database":
            name = arguments.get("name", "db")
            region = arguments.get("region", "unknown")
            return _result(
                {
                    "connection_string": f"postgres://admin:s3cr3t@{region}.example.net/{name}",
                    "id": f"db-{name}",
                }
            )
        if params.name == "list_env_vars":
            return _result({"variables": [f"{k}={v}" for k, v in ENV_VARS.items()]})
        if params.name == "set_env_var":
            ENV_VARS[str(arguments.get("key"))] = str(arguments.get("value"))
            return _result({"status": "ok"})
        if params.name == "delete_database":
            return _result({"status": "deleted"})

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"unknown tool {params.name}")],
            isError=True,
        )

    server = build_lowlevel(on_list_tools, on_call_tool)
    server.recorder = recorder  # type: ignore[attr-defined]
    return server


def build_lowlevel(on_list_tools: Any, on_call_tool: Any) -> Server[Any]:
    return Server(
        "demo-paas",
        version="0.1.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
