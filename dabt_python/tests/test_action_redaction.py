from pathlib import Path

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import validate_manifest_payload
from dabt_core.schema import Decision

ROOT = Path(__file__).parents[1] / "dabt_core" / "data"
TIMESTAMP = "2026-08-18T09:00:00Z"


def verified_manifest():
    """A transcribed-quality manifest, so ALLOW paths are reachable in tests."""
    return validate_manifest_payload(
        {
            "version": "test-verified",
            "server": {"id": "cranl"},
            "tools": {
                "set_env_var": {
                    "operation": "update",
                    "resource_type": "configuration",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {
                        "key": {"role": "resource_name", "maskable": False},
                        "value": {"role": "opaque_payload", "maskable": True},
                        "replicas": {"role": "opaque_payload", "maskable": True},
                    },
                },
                "list_env_vars": {
                    "operation": "read",
                    "resource_type": "configuration",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "returns": {
                        "variables": {
                            "role": "opaque_payload",
                            "inspect_content": True,
                            "collection": True,
                            "maskable": True,
                        }
                    },
                },
                "delete_database": {
                    "operation": "delete",
                    "resource_type": "database",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {"name": {"role": "resource_name", "maskable": False}},
                },
                "create_database": {
                    "operation": "create",
                    "resource_type": "database",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {"name": {"role": "resource_name", "maskable": False}},
                    "returns": {
                        "connection_string": {
                            "role": "credential",
                            "declared_sensitive": True,
                            "maskable": True,
                        }
                    },
                },
            },
        }
    )


def engine() -> ActionEngine:
    manifest = verified_manifest()
    return ActionEngine(load_compliance_map(ROOT / "compliance_map.yaml"), {manifest.server_id: manifest})


def test_manifested_action_with_no_findings_allows() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="delete_database", arguments={"name": "production"}),
        TIMESTAMP,
    )
    assert result.decision == Decision.ALLOW
    assert result.decision_rule_id == "ACTION-DEFAULT-ALLOW-NO-FINDING"
    assert result.rewritten is False
    assert result.released_arguments == {"name": "production"}


def test_rewritten_flag_set_when_arguments_altered() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl", tool="set_env_var", arguments={"key": "K", "value": "id 1000000008"}
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.ALLOW_WITH_REDACTION
    assert result.rewritten is True
    assert "1000000008" not in result.released_arguments["value"]
    assert result.released_arguments["key"] == "K"


def test_untouched_arguments_keep_their_original_type() -> None:
    # Flattening stringifies for scanning; a released argument that was never
    # masked must come back as the caller sent it, not as its str() form.
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="set_env_var",
            arguments={"key": "K", "value": "clean", "replicas": 3},
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.ALLOW
    assert result.released_arguments["replicas"] == 3
    assert isinstance(result.released_arguments["replicas"], int)


def test_denied_action_releases_no_arguments() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="set_env_var",
            arguments={"key": "K", "value": "medical diagnosis on file"},
            lawful_basis="legitimate_interest",
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.DENY
    assert result.released_arguments is None


def test_collection_redacts_only_flagged_elements() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean one", "iban SA0380000000608010167519", "clean two"]},
        ),
        TIMESTAMP,
    )
    released = result.released_result["variables"]
    assert released[0] == "clean one"
    assert released[2] == "clean two"
    assert "SA0380000000608010167519" not in released[1]


def test_collection_classification_aggregates_to_maximum() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean", "medical diagnosis attached"]},
        ),
        TIMESTAMP,
    )
    assert result.classification == "Secret"


def test_collection_deny_withholds_every_element() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean", "medical diagnosis attached"]},
            lawful_basis="legitimate_interest",
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.DENY
    assert result.released_result is None


def test_undeclared_response_field_reviews() -> None:
    # Nothing inspected it, so it must not be permitted merely by not being looked at.
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl", tool="list_env_vars", result={"surprise_field": "anything at all"}
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW
    assert result.released_result is None


def test_write_tool_response_disclosure_is_gated() -> None:
    # The write proceeds; the credential it returns does not reach the model.
    gate = engine()

    permitted = gate.evaluate(
        ActionRequest(server_id="cranl", tool="create_database", arguments={"name": "customers"}),
        TIMESTAMP,
    )
    assert permitted.decision == Decision.ALLOW

    withheld = gate.evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="create_database",
            result={"connection_string": "postgres://u:secret@host/db"},
        ),
        TIMESTAMP,
    )
    assert withheld.decision == Decision.REVIEW
    assert withheld.released_result is None
