"""Translation between MCP's response shape and the shape the engine gates."""

from __future__ import annotations

import json

from conftest import FakeUpstream, build_gate
from mcp import types

from dabt_proxy.adapter import TEXT_FIELD, restore, to_envelope
from dabt_proxy.outcome import ToolResponse

IBAN = "SA0380000000608010167519"


def text_block(text: str) -> types.TextContent:
    return types.TextContent(type="text", text=text)


def test_structured_content_is_gated_directly():
    envelope = to_envelope(ToolResponse(structured={"connection_string": "x"}))

    assert envelope.source == "structured"
    assert envelope.payload == {"connection_string": "x"}


def test_text_only_response_is_gated_under_mcps_own_field_name():
    envelope = to_envelope(ToolResponse(blocks=(text_block("a"), text_block("b"))))

    assert envelope.source == "text"
    assert envelope.payload == {TEXT_FIELD: ["a", "b"]}


def test_empty_response_gates_nothing():
    """No disclosure means nothing to withhold; forcing REVIEW here would be noise."""
    envelope = to_envelope(ToolResponse())

    assert envelope.source == "empty"
    assert envelope.payload == {}


def test_non_text_blocks_are_reported_as_uninspectable():
    class ImageBlock:
        type = "image"

    envelope = to_envelope(ToolResponse(blocks=(text_block("a"), ImageBlock())))

    assert envelope.uninspectable is True
    assert envelope.uninspectable_block_types == ("image",)


def test_untouched_response_passes_through_byte_for_byte():
    original = ToolResponse(structured={"a": 1}, blocks=(text_block('{"a": 1}'),))
    envelope = to_envelope(original)

    restored = restore(original, envelope, {"a": 1}, rewritten=False)

    assert restored is original


def test_redacted_structure_is_not_leaked_through_the_mirrored_text_block():
    """The trap this module exists to avoid.

    Servers that return `structuredContent` normally mirror it as serialised
    text. Substituting only the structure would return the masked value in one
    field and the original secret in the other - a proxy reporting a redaction
    it did not perform.
    """
    original = ToolResponse(
        structured={"variables": [f"IBAN={IBAN}"]},
        blocks=(text_block(json.dumps({"variables": [f"IBAN={IBAN}"]})),),
    )
    envelope = to_envelope(original)

    restored = restore(original, envelope, {"variables": ["IBAN=████"]}, rewritten=True)

    assert IBAN not in json.dumps(restored.structured)
    for block in restored.blocks:
        assert IBAN not in block.text


def test_redacted_text_response_rebuilds_its_blocks():
    original = ToolResponse(blocks=(text_block(f"IBAN={IBAN}"), text_block("PORT=8080")))
    envelope = to_envelope(original)

    restored = restore(original, envelope, {TEXT_FIELD: ["IBAN=████", "PORT=8080"]}, rewritten=True)

    assert [block.text for block in restored.blocks] == ["IBAN=████", "PORT=8080"]
    assert IBAN not in "".join(block.text for block in restored.blocks)


async def test_gate_does_not_leak_the_secret_through_mirrored_text(policy):
    """The same trap, end to end through the real engine rather than in isolation."""
    payload = {"variables": ["PORT=8080", f"BILLING_IBAN={IBAN}"]}
    upstream = FakeUpstream(
        ToolResponse(structured=payload, blocks=(text_block(json.dumps(payload)),))
    )
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("list_env_vars", {"app_id": "app-1"})

    assert outcome.decision == "ALLOW_WITH_REDACTION"
    released = outcome.released
    assert IBAN not in json.dumps(released.structured, ensure_ascii=False)
    for block in released.blocks:
        assert IBAN not in block.text
