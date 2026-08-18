"""How an outcome reaches the agent, and what the audit log is allowed to contain."""

from __future__ import annotations

import io
import json

from conftest import FakeUpstream, build_gate

from dabt_proxy.outcome import ToolResponse
from dabt_proxy.server import AuditSink, audit_entry, refusal_text, to_mcp_result, utc_now

IBAN = "SA0380000000608010167519"
SECRET = "postgres://admin:s3cr3t@me-central-1.example.net/customers"


async def test_a_blocked_call_is_returned_as_a_tool_error(policy):
    gate = build_gate(policy, FakeUpstream())
    outcome = await gate.call_tool("create_database", {"region": "eu-west-1", "name": "c"})

    result = to_mcp_result(outcome)

    assert result.is_error is True
    text = result.content[0].text
    assert "PDPL-ART29-2C-INFERRED-RESIDENCY" in text
    assert "EN:" in text and "AR:" in text


async def test_the_refusal_names_the_rule_and_its_confidence(policy):
    gate = build_gate(policy, FakeUpstream())
    outcome = await gate.call_tool("create_database", {"region": "eu-west-1", "name": "c"})

    text = refusal_text(outcome)

    assert "PDPL" in text
    assert "mapping confidence: needs_verification" in text
    assert "requires qualified Saudi legal or compliance review" in text


async def test_a_response_leg_refusal_says_the_side_effect_stands(policy):
    """An agent that retries a completed write because the gate was vague is a bug."""
    upstream = FakeUpstream(ToolResponse(structured={"connection_string": SECRET, "id": "db-1"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("create_database", {"region": "me-central-1", "name": "c"})
    text = refusal_text(outcome)

    assert "already been forwarded" in text
    assert SECRET not in text


async def test_a_rewritten_release_tells_the_agent_it_was_altered(policy):
    """Without this an agent proceeds believing it read the original value."""
    upstream = FakeUpstream(
        ToolResponse(structured={"variables": ["PORT=8080", f"IBAN={IBAN}"]})
    )
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("list_env_vars", {"app_id": "app-1"})
    result = to_mcp_result(outcome)

    combined = " ".join(block.text for block in result.content)
    assert "masked, not the originals" in combined
    assert IBAN not in combined


async def test_a_clean_call_is_not_annotated(policy):
    upstream = FakeUpstream(ToolResponse(structured={"status": "deleted"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "production"})
    result = to_mcp_result(outcome)

    assert result.is_error is False
    assert "masked" not in " ".join(block.text for block in result.content)


async def test_the_audit_record_does_not_contain_what_it_withheld(policy):
    """Moving a secret into the log is moving the leak, not closing it."""
    upstream = FakeUpstream(ToolResponse(structured={"connection_string": SECRET, "id": "db-1"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("create_database", {"region": "me-central-1", "name": "c"})
    serialised = json.dumps(audit_entry(outcome, utc_now()), ensure_ascii=False)

    assert SECRET not in serialised
    assert "s3cr3t" not in serialised
    # It still says what happened and on what grounds.
    assert "NCA-ECC-CREDENTIAL-DISCLOSURE" in serialised


async def test_the_audit_record_names_findings_without_quoting_them(policy):
    upstream = FakeUpstream(ToolResponse(structured={"variables": [f"IBAN={IBAN}"]}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("list_env_vars", {"app_id": "app-1"})
    entry = audit_entry(outcome, utc_now())

    assert entry["findings"], "a finding was made and should be recorded"
    assert entry["findings"][0]["type"] == "saudi_iban"
    assert IBAN not in json.dumps(entry, ensure_ascii=False)


async def test_the_audit_record_carries_both_languages_and_both_versions(policy):
    gate = build_gate(policy, FakeUpstream())
    outcome = await gate.call_tool("create_database", {"region": "eu-west-1", "name": "c"})

    entry = audit_entry(outcome, utc_now())

    assert entry["reason_en"] and entry["reason_ar"]
    assert entry["legal_review_disclaimer_en"] and entry["legal_review_disclaimer_ar"]
    assert entry["policy_map_version"]
    assert entry["manifest_version"] == "0.1.0-demo-paas"


def test_audit_records_go_to_the_given_stream_not_stdout(capsys):
    """stdout is MCP framing; a stray byte there corrupts the protocol."""
    stream = io.StringIO()
    AuditSink(stream=stream).write({"decision": "REVIEW", "reason_ar": "مراجعة"})

    assert json.loads(stream.getvalue())["decision"] == "REVIEW"
    assert capsys.readouterr().out == ""


def test_audit_records_are_written_as_readable_arabic(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditSink(stream=io.StringIO(), path=path).write({"reason_ar": "لم تسمح البوابة"})

    assert "لم تسمح البوابة" in path.read_text(encoding="utf-8")
