from pathlib import Path

from dabt_core.action import ActionEngine, ActionRequest
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest
from dabt_core.schema import Decision

ROOT = Path(__file__).parents[1] / "dabt_core" / "data"
TIMESTAMP = "2026-08-18T09:00:00Z"


def engine() -> ActionEngine:
    manifest = load_manifest(ROOT / "manifests" / "cranl.yaml")
    return ActionEngine(load_compliance_map(ROOT / "compliance_map.yaml"), {manifest.server_id: manifest})


def test_unmanifested_tool_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="no_such_tool", arguments={"x": "y"}), TIMESTAMP
    )
    assert result.decision == Decision.REVIEW


def test_unknown_server_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="not_a_server", tool="create_database", arguments={}), TIMESTAMP
    )
    assert result.decision == Decision.REVIEW


def test_reconstructed_cranl_manifest_cannot_reach_allow() -> None:
    # Every CranL entry is needs_verification, so nothing there may be permitted
    # until the real tool schema is transcribed.
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="delete_database", arguments={"name": "production"}),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW


def test_personal_data_in_an_argument_fires_an_existing_pdpl_rule() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="set_env_var",
            arguments={"key": "OWNER_ID", "value": "national id 1000000008"},
        ),
        TIMESTAMP,
    )
    assert result.classification == "Confidential"
    assert "PDPL-ART11-3-MINIMISATION" in {rule.id for rule in result.fired_rules}


def test_provisioning_outside_the_kingdom_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="create_database",
            arguments={"region": "eu-west-1", "name": "customers"},
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW
    assert result.decision_rule_id == "PDPL-ART29-2C-INFERRED-RESIDENCY"


def test_provisioning_inside_the_kingdom_does_not_fire_the_residency_rule() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="create_database",
            arguments={"region": "me-central-1", "name": "customers"},
        ),
        TIMESTAMP,
    )
    assert "PDPL-ART29-2C-INFERRED-RESIDENCY" not in {rule.id for rule in result.fired_rules}


def test_action_evaluation_is_deterministic() -> None:
    request = ActionRequest(
        server_id="cranl", tool="set_env_var", arguments={"key": "K", "value": "id 1000000008"}
    )
    first = engine().evaluate(request, TIMESTAMP).to_dict()
    second = engine().evaluate(request, TIMESTAMP).to_dict()
    assert first == second


def test_audit_record_carries_both_languages() -> None:
    result = engine().evaluate(ActionRequest(server_id="cranl", tool="get_logs", arguments={}), TIMESTAMP)
    assert result.audit.legal_review_disclaimer_en
    assert "مراجعة" in result.audit.legal_review_disclaimer_ar


def test_manifest_version_is_reported() -> None:
    result = engine().evaluate(ActionRequest(server_id="cranl", tool="get_logs", arguments={}), TIMESTAMP)
    assert result.manifest_version == "0.1.0-cranl-reconstructed"
