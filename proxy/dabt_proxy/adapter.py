"""Translation between MCP's response shape and the shape the engine gates.

The engine gates response fields *by manifest-declared name*. MCP returns
`content: [ContentBlock]` plus an optional `structuredContent` object. Bridging
the two is the only genuinely subtle code in the proxy, and it is subtle in a
direction that matters: the obvious implementation leaks the exact value the
product exists to withhold. See `restore`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mcp import types

from .outcome import ToolResponse

# MCP's own name for the unstructured half of a response. A manifest that wants
# text-returning tools gated declares a return field under this name; one that
# does not leaves it undeclared, and an undeclared field cannot reach ALLOW.
TEXT_FIELD = "content"


@dataclass(frozen=True)
class ResponseEnvelope:
    """What the proxy hands the engine, plus what it needs to reassemble later."""

    payload: dict[str, Any]
    source: str  # "structured" | "text" | "empty"
    uninspectable_block_types: tuple[str, ...] = ()

    @property
    def uninspectable(self) -> bool:
        return bool(self.uninspectable_block_types)


def _text_of(block: Any) -> str | None:
    """The text of a text block, or None for any block the detectors cannot read."""
    if isinstance(block, types.TextContent):
        return block.text
    # Duck-typed so a fake upstream in a test need not construct MCP models.
    if getattr(block, "type", None) == "text" and isinstance(getattr(block, "text", None), str):
        return block.text
    return None


def to_envelope(response: ToolResponse) -> ResponseEnvelope:
    """Normalise an upstream response into the dict the engine evaluates.

    Three cases, and the choice between them decides what the engine can
    conclude:

    * `structuredContent` present -> gate it directly. Its keys are the names
      the manifest declares, so declared fields are inspected and undeclared
      ones trip the engine's undeclared-field guard.
    * text only -> gate `{"content": [...]}`. If the manifest declares
      `content`, every block is scanned as a collection. If it does not, the
      engine sees an undeclared field and resolves to REVIEW. Either way the
      text is never released unexamined.
    * nothing returned -> gate `{}`. Nothing was disclosed, so there is nothing
      to withhold, and forcing REVIEW on an empty acknowledgement would make
      the gate unusable for write tools that return no payload.
    """
    uninspectable = tuple(
        str(getattr(block, "type", type(block).__name__))
        for block in response.blocks
        if _text_of(block) is None
    )

    if response.structured is not None:
        return ResponseEnvelope(dict(response.structured), "structured", uninspectable)

    texts = [text for block in response.blocks if (text := _text_of(block)) is not None]
    if not texts and not uninspectable:
        return ResponseEnvelope({}, "empty", ())
    return ResponseEnvelope({TEXT_FIELD: texts}, "text", uninspectable)


def restore(
    response: ToolResponse, envelope: ResponseEnvelope, released: dict[str, Any], rewritten: bool
) -> ToolResponse:
    """Rebuild an upstream response from what the engine agreed to release.

    The trap: a server that returns `structuredContent` normally also returns
    the same data serialised as text, for clients that predate structured
    output. Substituting only the redacted structure would return the redacted
    value in one field and the original secret in the other - a proxy that
    reports a redaction it did not perform. So when the engine rewrote
    anything, the text blocks are regenerated from the released structure
    rather than passed through.

    When nothing was rewritten the original blocks are returned untouched, so a
    clean call is a byte-for-byte passthrough.
    """
    if envelope.source == "empty" or not rewritten:
        return response

    if envelope.source == "structured":
        serialised = json.dumps(released, ensure_ascii=False, default=str)
        return ToolResponse(
            structured=released,
            blocks=(types.TextContent(type="text", text=serialised),),
            is_error=response.is_error,
        )

    released_texts = released.get(TEXT_FIELD) or []
    return ToolResponse(
        structured=response.structured,
        blocks=tuple(
            types.TextContent(type="text", text=text if isinstance(text, str) else str(text))
            for text in released_texts
        ),
        is_error=response.is_error,
    )


def from_call_tool_result(result: Any) -> ToolResponse:
    """Read an MCP `CallToolResult` into the proxy's normalised shape."""
    return ToolResponse(
        structured=getattr(result, "structured_content", None),
        blocks=tuple(getattr(result, "content", ()) or ()),
        is_error=bool(getattr(result, "is_error", False)),
    )


def to_call_tool_result(response: ToolResponse) -> types.CallToolResult:
    """Render the proxy's normalised shape back onto the MCP wire."""
    return types.CallToolResult(
        content=list(response.blocks),
        structuredContent=response.structured,
        isError=response.is_error,
    )
