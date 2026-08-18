"""The action surface's audit record must describe an action.

One engine serves two surfaces and one audit builder serves both. Without a
surface argument the record described every tool call as a retrieval, and it
was sealed before obligations were resolved, so it reported no redactions even
when it had masked a value. Both made the record misstate the event it exists
to evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest
from dabt_core.schema import Decision

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"
MANIFEST_DIR = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests"
TIMESTAMP = "2026-08-18T09:00:00+00:00"
IBAN = "SA0380000000608010167519"

VERIFIED_MANIFEST = """
version: "0.1.0-audit-fixture"
server:
  id: audit-fixture
  description: "Fixture server for audit record assertions"
tools:
  set_env_var:
    operation: update
    resource_type: configuration
    persists_data: true
    confidence_level: verified
    requires_legal_review: true
    parameters:
      key: { role: resource_name, maskable: false }
      value: { role: opaque_payload, maskable: true }
    returns:
      variables:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true
""".strip()


@pytest.fixture(scope="module")
def engine(tmp_path_factory: pytest.TempPathFactory) -> ActionEngine:
    path = tmp_path_factory.mktemp("manifests") / "audit-fixture.yaml"
    path.write_text(VERIFIED_MANIFEST, encoding="utf-8")
    manifests = {
        manifest.server_id: manifest
        for manifest in (load_manifest(item) for item in sorted(MANIFEST_DIR.glob("*.yaml")))
    }
    manifests["audit-fixture"] = load_manifest(path)
    return ActionEngine(load_compliance_map(MAP_PATH), manifests)


def evaluate(engine: ActionEngine, **arguments: str):
    return engine.evaluate(
        ActionRequest(server_id="audit-fixture", tool="set_env_var", arguments=arguments),
        TIMESTAMP,
    )


def test_the_record_names_the_tool_call_not_a_retrieval(engine: ActionEngine) -> None:
    audit = evaluate(engine, key="PORT", value="8080").audit

    assert "retrieval" not in audit.summary_en
    assert "the tool call 'set_env_var'" in audit.summary_en
    assert "الاسترجاع" not in audit.summary_ar
    assert "set_env_var" in audit.summary_ar


def test_the_record_counts_the_redactions_it_performed(engine: ActionEngine) -> None:
    """Sealing the record before obligations resolved reported zero every time."""
    result = evaluate(engine, key="PAYOUT", value=IBAN)

    assert result.decision == Decision.ALLOW_WITH_REDACTION
    assert len(result.obligations) == 1
    assert "1 redaction obligation(s) were resolved" in result.audit.summary_en
    assert "وتم تحديد 1 من التزامات الحجب" in result.audit.summary_ar


def test_a_clean_call_still_reports_no_redactions(engine: ActionEngine) -> None:
    result = evaluate(engine, key="PORT", value="8080")

    assert result.obligations == ()
    assert "0 redaction obligation(s) were resolved" in result.audit.summary_en


def test_the_response_leg_record_also_names_the_tool_call(engine: ActionEngine) -> None:
    result = engine.evaluate_result(
        ActionResultRequest(
            server_id="audit-fixture",
            tool="set_env_var",
            result={"variables": ["PORT=8080", f"IBAN={IBAN}"]},
        ),
        TIMESTAMP,
    )

    assert "the tool call 'set_env_var'" in result.audit.summary_en
    assert "retrieval" not in result.audit.summary_en
    assert "1 redaction obligation(s) were resolved" in result.audit.summary_en


def test_an_unmanifested_tool_still_produces_a_coherent_record(engine: ActionEngine) -> None:
    """No spec means no tool name is trusted, but the record must still read correctly."""
    result = engine.evaluate(
        ActionRequest(server_id="audit-fixture", tool="unknown_tool", arguments={}), TIMESTAMP
    )

    assert "the tool call 'unknown_tool'" in result.audit.summary_en
    assert "retrieval" not in result.audit.summary_en


def test_the_retrieval_surface_is_unchanged() -> None:
    """The other surface must keep describing itself as a retrieval."""
    from dabt_core.engine import EngineRequest, PolicyEngine

    result = PolicyEngine(load_compliance_map(MAP_PATH)).evaluate(
        EngineRequest(document="Nothing regulated here."), TIMESTAMP
    )

    assert "Dabt evaluated the retrieval as" in result.audit.summary_en
    assert "طلب الاسترجاع" in result.audit.summary_ar
