import pytest

from dabt_core.manifest import ManifestError, validate_manifest_payload


def base_tool() -> dict:
    return {
        "operation": "create",
        "resource_type": "database",
        "persists_data": True,
        "confidence_level": "needs_verification",
        "requires_legal_review": True,
        "parameters": {
            "region": {"role": "deployment_region", "maskable": False},
        },
        "returns": {
            "connection_string": {
                "role": "credential",
                "declared_sensitive": True,
                "maskable": True,
            }
        },
    }


def payload_with(tool: dict) -> dict:
    return {"version": "0.1", "server": {"id": "cranl"}, "tools": {"create_database": tool}}


def test_valid_manifest_is_accepted() -> None:
    manifest = validate_manifest_payload(payload_with(base_tool()))
    assert manifest.server_id == "cranl"
    spec = manifest.tool("create_database")
    assert spec is not None
    assert spec.operation == "create"
    assert spec.persists_data is True
    assert manifest.parameter("create_database", "region").role == "deployment_region"


def test_unknown_tool_returns_none() -> None:
    manifest = validate_manifest_payload(payload_with(base_tool()))
    assert manifest.tool("no_such_tool") is None


def test_tool_requires_confidence_level() -> None:
    tool = base_tool()
    tool.pop("confidence_level")
    with pytest.raises(ManifestError, match="create_database.*confidence_level"):
        validate_manifest_payload(payload_with(tool))


def test_tool_requires_legal_review_true() -> None:
    tool = base_tool()
    tool["requires_legal_review"] = False
    with pytest.raises(ManifestError, match="create_database.*requires_legal_review"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_request_role_is_rejected() -> None:
    tool = base_tool()
    tool["parameters"]["region"]["role"] = "not_a_real_role"
    with pytest.raises(ManifestError, match="region.*role"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_response_role_is_rejected() -> None:
    tool = base_tool()
    tool["returns"]["connection_string"]["role"] = "deployment_region"
    with pytest.raises(ManifestError, match="connection_string.*role"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_operation_is_rejected() -> None:
    tool = base_tool()
    tool["operation"] = "teleport"
    with pytest.raises(ManifestError, match="create_database.*operation"):
        validate_manifest_payload(payload_with(tool))


def test_declared_sensitive_defaults_to_false() -> None:
    tool = base_tool()
    tool["returns"]["connection_string"].pop("declared_sensitive")
    manifest = validate_manifest_payload(payload_with(tool))
    field = manifest.tool("create_database").returns[0]
    assert field.declared_sensitive is False
    assert field.inspect_content is False
    assert field.collection is False
