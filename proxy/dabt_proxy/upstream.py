"""The gated server, reached over whichever transport it actually speaks.

Nothing here knows which vendor is on the other end. An upstream is a command to
spawn, a URL to call, or - in tests - an in-process server object, and all three
arrive as the same `UpstreamClient` to the gate.
"""

from __future__ import annotations

import shlex
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping

from mcp import Client, StdioServerParameters, stdio_client

from .adapter import from_call_tool_result
from .outcome import ToolResponse


class UpstreamError(RuntimeError):
    """The gated server could not be reached, or refused the call."""


@dataclass(frozen=True)
class StdioUpstream:
    """A locally spawned MCP server."""

    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    cwd: str | None = None

    @classmethod
    def from_command_line(cls, command_line: str, **kwargs: Any) -> StdioUpstream:
        parts = shlex.split(command_line, posix=True)
        if not parts:
            raise ValueError("upstream stdio command line is empty")
        return cls(command=parts[0], args=tuple(parts[1:]), **kwargs)

    def describe(self) -> str:
        return " ".join((self.command, *self.args))

    def transport(self) -> Any:
        return stdio_client(
            StdioServerParameters(
                command=self.command,
                args=list(self.args),
                env=dict(self.env) if self.env else None,
                cwd=self.cwd,
            )
        )


@dataclass(frozen=True)
class HttpUpstream:
    """A hosted MCP server speaking streamable HTTP."""

    url: str

    def describe(self) -> str:
        return self.url


@dataclass(frozen=True)
class InProcessUpstream:
    """An MCP server object in this process. Used by the tests and the demo."""

    server: Any = field(repr=False)
    label: str = "in-process"

    def describe(self) -> str:
        return self.label


UpstreamTarget = StdioUpstream | HttpUpstream | InProcessUpstream


class McpUpstream:
    """Adapts a connected `mcp.Client` to the gate's `UpstreamClient` protocol."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_tools(self) -> Any:
        try:
            return await self._client.list_tools()
        except Exception as error:  # noqa: BLE001
            raise UpstreamError(str(error)) from error

    async def call_tool(self, tool: str, arguments: Mapping[str, Any]) -> ToolResponse:
        try:
            result = await self._client.call_tool(tool, dict(arguments))
        except Exception as error:  # noqa: BLE001
            raise UpstreamError(str(error)) from error
        return from_call_tool_result(result)


@asynccontextmanager
async def connect(target: UpstreamTarget) -> AsyncIterator[McpUpstream]:
    """Open a session to the gated server for the lifetime of the context."""
    if isinstance(target, HttpUpstream):
        server: Any = target.url
    elif isinstance(target, InProcessUpstream):
        server = target.server
    else:
        server = target.transport()

    async with Client(server) as client:
        yield McpUpstream(client)
