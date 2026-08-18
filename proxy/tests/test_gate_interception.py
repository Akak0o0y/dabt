"""The guarantees the gate exists to provide, against the real policy engine.

These use the real compliance map, the real manifest loader and the real
`ActionEngine`. Only the upstream is a fake, because the assertion that matters
is what did or did not reach it.
"""

from __future__ import annotations

from conftest import FakeUpstream, build_gate

from dabt_proxy.outcome import ToolResponse


async def test_denied_call_never_reaches_upstream(policy):
    """A blocked request leg is the only place a side effect can be prevented."""
    upstream = FakeUpstream()
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool(
        "create_database", {"region": "eu-west-1", "name": "customers", "replicas": 3}
    )

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert outcome.leg == "request"
    assert outcome.decision_rule_id == "PDPL-ART29-2C-INFERRED-RESIDENCY"
    assert outcome.dispatched is False
    # The point of the whole exercise.
    assert upstream.calls == []


async def test_blocked_call_states_its_grounds_in_both_languages(policy):
    gate = build_gate(policy, FakeUpstream())

    outcome = await gate.call_tool("create_database", {"region": "eu-west-1", "name": "c"})

    assert outcome.reason_en and outcome.reason_ar
    assert outcome.reason_en != outcome.reason_ar
    # Arabic, not merely present: the refusal must contain Arabic script.
    assert any("؀" <= character <= "ۿ" for character in outcome.reason_ar)
    assert outcome.citation is not None
    assert outcome.citation["framework"] == "PDPL"
    assert outcome.legal_review_disclaimer_en and outcome.legal_review_disclaimer_ar


async def test_clean_destructive_call_is_allowed(policy):
    """Scope boundary: Dabt gates regulatory violations, not blast radius.

    A clean `delete_database` carries no Saudi personal data and breaches no
    mapped provision, so it passes. Pretending otherwise would be the overreach
    the design spec forbids.
    """
    upstream = FakeUpstream(ToolResponse(structured={"status": "deleted"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "production"})

    assert outcome.blocked is False
    assert outcome.decision == "ALLOW"
    assert upstream.calls == [("delete_database", {"name": "production"})]


async def test_redacted_arguments_are_what_reach_upstream(policy):
    """The upstream must receive the masked value, never the original."""
    upstream = FakeUpstream(ToolResponse(structured={"status": "ok"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool(
        "set_env_var", {"key": "BILLING", "value": "SA0380000000608010167519"}
    )

    assert outcome.blocked is False
    assert outcome.rewritten_arguments is True
    (_, forwarded), = upstream.calls
    assert "SA0380000000608010167519" not in forwarded["value"]
    assert forwarded["key"] == "BILLING"


async def test_unmasked_arguments_keep_their_type(policy):
    """Flattening stringifies for scanning; the forwarded call must not inherit that."""
    upstream = FakeUpstream(ToolResponse(structured={"status": "ok"}))
    gate = build_gate(policy, upstream)

    await gate.call_tool("create_database", {"region": "me-central-1", "name": "c", "replicas": 3})

    (_, forwarded), = upstream.calls
    assert forwarded["replicas"] == 3
    assert not isinstance(forwarded["replicas"], str)


async def test_declared_credential_is_withheld_after_the_write_completes(policy):
    """The response leg cannot unwind the write, but still stops the credential.

    This is the demonstration in executable form: the database is created, and
    the connection string does not reach the model.
    """
    secret = "postgres://admin:s3cr3t@me-central-1.example.net/customers"
    upstream = FakeUpstream(ToolResponse(structured={"connection_string": secret, "id": "db-1"}))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool(
        "create_database", {"region": "me-central-1", "name": "customers"}
    )

    assert upstream.was_called is True, "the write should have been permitted"
    assert outcome.blocked is True
    assert outcome.leg == "response"
    assert outcome.decision_rule_id == "NCA-ECC-CREDENTIAL-DISCLOSURE"
    assert outcome.dispatched is True, "the caller must be told the side effect stands"
    assert outcome.released is None
    assert secret not in outcome.reason_en
    assert secret not in str(outcome.audit)


async def test_collection_redacts_only_flagged_elements(policy):
    """Per-element redaction: the clean variables survive intact."""
    upstream = FakeUpstream(
        ToolResponse(
            structured={
                "variables": [
                    "PORT=8080",
                    "BILLING_IBAN=SA0380000000608010167519",
                    "LOG_LEVEL=info",
                ]
            }
        )
    )
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("list_env_vars", {"app_id": "app-1"})

    assert outcome.blocked is False
    assert outcome.decision == "ALLOW_WITH_REDACTION"
    released = outcome.released.structured["variables"]
    assert released[0] == "PORT=8080"
    assert released[2] == "LOG_LEVEL=info"
    assert "SA0380000000608010167519" not in released[1]


async def test_collection_classification_aggregates_to_maximum(policy):
    """NDMO Principle 4 across elements: one finding lifts the whole response."""
    upstream = FakeUpstream(
        ToolResponse(structured={"variables": ["PORT=8080", "IBAN=SA0380000000608010167519"]})
    )
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("list_env_vars", {"app_id": "app-1"})

    assert outcome.classification == "Confidential"


async def test_unstructured_response_is_reviewed_not_released(policy):
    """A text-only response is an undeclared field here, so it cannot reach ALLOW."""

    class Block:
        type = "text"
        text = "Riyadh office contact 0512345678"

    upstream = FakeUpstream(ToolResponse(structured=None, blocks=(Block(),)))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "db"})

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert outcome.leg == "response"


async def test_empty_response_is_released(policy):
    """Nothing was disclosed, so there is nothing to withhold."""
    upstream = FakeUpstream(ToolResponse(structured=None, blocks=()))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "db"})

    assert outcome.blocked is False
    assert outcome.decision == "ALLOW"


async def test_uninspectable_content_is_held_for_review(policy):
    """An image cannot be scanned, so it is not released as if it had been."""

    class ImageBlock:
        type = "image"

    upstream = FakeUpstream(ToolResponse(structured=None, blocks=(ImageBlock(),)))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "db"})

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert "image" in outcome.reason_en
    assert any("؀" <= character <= "ۿ" for character in outcome.reason_ar)


async def test_upstream_failure_is_not_reported_as_a_side_effect_that_completed(policy):
    """Dabt cannot know whether a failed call took effect, and must not claim to."""
    upstream = FakeUpstream(error=RuntimeError("connection reset"))
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("delete_database", {"name": "db"})

    assert outcome.blocked is True
    assert outcome.decision == "UPSTREAM_ERROR"
    assert outcome.dispatched is True
    assert "unknown" in outcome.reason_en.lower()


async def test_unmanifested_tool_is_never_allowed(policy):
    """A tool the manifest never described cannot be reasoned about, so it waits."""
    upstream = FakeUpstream()
    gate = build_gate(policy, upstream)

    outcome = await gate.call_tool("undeclared_tool", {"anything": "here"})

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert upstream.calls == []


async def test_unverified_manifest_holds_every_call(policy):
    """The packaged CranL manifest is a reconstruction, so nothing against it releases."""
    upstream = FakeUpstream()
    gate = build_gate(policy, upstream, server_id="cranl")

    outcome = await gate.call_tool("delete_database", {"name": "production"})

    assert outcome.blocked is True
    assert outcome.decision == "REVIEW"
    assert upstream.calls == []


async def test_evaluation_is_deterministic(policy):
    """Same input twice, same decision - the retrieval surface's guarantee, kept."""
    first = await build_gate(policy, FakeUpstream()).call_tool(
        "create_database", {"region": "eu-west-1", "name": "c"}
    )
    second = await build_gate(policy, FakeUpstream()).call_tool(
        "create_database", {"region": "eu-west-1", "name": "c"}
    )

    assert first == second
