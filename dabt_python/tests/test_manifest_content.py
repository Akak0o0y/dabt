from pathlib import Path

from dabt_core.manifest import load_manifest
from dabt_core.schema import ConfidenceLevel

MANIFEST_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests" / "cranl.yaml"


def test_cranl_manifest_loads() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    assert manifest.server_id == "cranl"
    assert len(manifest.tools) >= 4


def test_no_cranl_tool_claims_verified_confidence() -> None:
    # Nobody has transcribed CranL's published tool schema yet. Until that
    # happens the manifest is a reconstruction, and saying otherwise would be
    # the exact overreach this project exists to avoid.
    manifest = load_manifest(MANIFEST_PATH)
    for tool in manifest.tools:
        assert tool.confidence_level != ConfidenceLevel.VERIFIED, tool.name


def test_every_cranl_tool_requires_legal_review() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    for tool in manifest.tools:
        assert tool.requires_legal_review is True, tool.name


def test_create_database_declares_a_sensitive_response() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    tool = manifest.tool("create_database")
    assert tool is not None
    assert tool.declares_sensitive_response is True


def test_list_env_vars_is_an_inspected_collection() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    field = manifest.tool("list_env_vars").return_field("variables")
    assert field.inspect_content is True
    assert field.collection is True
