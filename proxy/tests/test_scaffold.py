"""Drafting a manifest for an organisation that does not have one yet."""

from __future__ import annotations

import yaml
from dabt_core.manifest import validate_manifest_payload
from fixtures.paas_server import TOOLS

from dabt_proxy.scaffold import draft_manifest, infer_operation, infer_parameter_role


def draft() -> str:
    return draft_manifest("acme", TOOLS, "https://mcp.acme.test/mcp")


def test_a_draft_is_a_valid_manifest():
    """It has to load, or it is a suggestion rather than a starting point."""
    manifest = validate_manifest_payload(yaml.safe_load(draft()))

    assert manifest.server_id == "acme"
    assert {tool.name for tool in manifest.tools} == {tool.name for tool in TOOLS}


def test_nothing_is_ever_drafted_as_verified():
    """An unreviewed draft must not be able to permit anything.

    The action ALLOW rule requires `tool_confidence: verified`, so every entry
    being `needs_verification` is what makes an inaccurate draft fail safe.
    """
    manifest = validate_manifest_payload(yaml.safe_load(draft()))

    assert {str(tool.confidence_level) for tool in manifest.tools} == {"needs_verification"}
    assert all(tool.requires_legal_review for tool in manifest.tools)


async def test_a_drafted_manifest_holds_every_call(compliance_map, tmp_path):
    """Proof of the previous test's claim, through the engine rather than by assertion."""
    from dabt_core.action import ActionEngine
    from dabt_core.manifest import load_manifest

    from conftest import FIXED_TIME, FakeUpstream, build_gate
    from dabt_proxy.policy import InProcessPolicyClient

    path = tmp_path / "acme.yaml"
    path.write_text(draft(), encoding="utf-8")
    manifest = load_manifest(path)

    engine = ActionEngine(compliance_map, {"acme": manifest})
    upstream = FakeUpstream()
    gate = build_gate(
        InProcessPolicyClient(engine, compliance_map.version), upstream, server_id="acme"
    )

    outcome = await gate.call_tool("delete_database", {"name": "anything"})

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert upstream.calls == []


def test_the_draft_says_it_is_a_draft():
    """A human has to know these fields are guesses before acting on them."""
    text = draft()

    assert "GENERATED, NOT TRANSCRIBED" in text
    assert "REVIEW:" in text
    assert "https://mcp.acme.test/mcp" in text


def test_operations_are_inferred_from_the_verb():
    assert infer_operation("create_database") == "create"
    assert infer_operation("list_env_vars") == "read"
    assert infer_operation("set_env_var") == "update"
    assert infer_operation("delete_database") == "delete"
    # No recognisable verb is not a licence to guess a read.
    assert infer_operation("frobnicate") == "execute"


def test_region_and_credential_parameters_are_recognised():
    assert infer_parameter_role("region") == "deployment_region"
    assert infer_parameter_role("availability_zone") == "deployment_region"
    assert infer_parameter_role("api_key") == "credential_reference"
    assert infer_parameter_role("app_id") == "resource_reference"
    assert infer_parameter_role("name") == "resource_name"
    assert infer_parameter_role("payload") == "opaque_payload"


def test_only_opaque_payloads_are_proposed_as_maskable():
    """Masking a region produces nonsense, not a redacted call."""
    manifest = validate_manifest_payload(yaml.safe_load(draft()))
    create = manifest.tool("create_database")

    assert create.parameter("region").maskable is False
    assert create.parameter("name").maskable is False
    assert create.parameter("replicas").maskable is True


def test_a_server_without_an_output_schema_gets_its_text_declared():
    """Otherwise a text-returning tool is undeclared, and every response reviews."""

    class TextOnlyTool:
        name = "search"
        description = "Search things"
        inputSchema = {"type": "object", "properties": {"q": {"type": "string"}}}
        outputSchema = None

    manifest = validate_manifest_payload(yaml.safe_load(draft_manifest("acme", [TextOnlyTool()], "x")))
    field = manifest.tool("search").return_field("content")

    assert field is not None
    assert field.inspect_content is True
    assert field.collection is True


def test_a_server_advertising_no_tools_produces_no_usable_manifest():
    text = draft_manifest("acme", [], "https://mcp.acme.test/mcp")

    assert "advertised no tools" in text
