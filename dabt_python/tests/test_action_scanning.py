from dabt_core.action import (
    ElementFinding,
    flatten_arguments,
    flatten_result,
    has_undeclared_fields,
    scan_elements,
)
from dabt_core.detectors import DEFAULT_DETECTORS
from dabt_core.manifest import validate_manifest_payload


def manifest():
    return validate_manifest_payload(
        {
            "version": "0.1",
            "server": {"id": "cranl"},
            "tools": {
                "set_env_var": {
                    "operation": "update",
                    "resource_type": "configuration",
                    "persists_data": True,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {
                        "key": {"role": "resource_name", "maskable": False},
                        "value": {"role": "opaque_payload", "maskable": True},
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
            },
        }
    )


def test_flatten_arguments_produces_element_paths() -> None:
    spec = manifest().tool("set_env_var")
    values = flatten_arguments(spec, {"key": "DB_URL", "value": "id 1000000008"})
    assert values == {"arguments.key": "DB_URL", "arguments.value": "id 1000000008"}


def test_flatten_result_indexes_collection_elements() -> None:
    spec = manifest().tool("list_env_vars")
    values = flatten_result(spec, {"variables": ["clean", "id 1000000008", "also clean"]})
    assert values == {
        "result.variables[0]": "clean",
        "result.variables[1]": "id 1000000008",
        "result.variables[2]": "also clean",
    }


def test_flatten_result_skips_fields_not_marked_for_inspection() -> None:
    spec = manifest().tool("set_env_var")
    assert flatten_result(spec, {"anything": "id 1000000008"}) == {}


def test_undeclared_response_field_is_reported() -> None:
    spec = manifest().tool("list_env_vars")
    assert has_undeclared_fields(spec, {"variables": ["clean"]}) is False
    assert has_undeclared_fields(spec, {"surprise": "anything"}) is True


def test_unmanifested_tool_reports_any_result_as_undeclared() -> None:
    assert has_undeclared_fields(None, {"anything": "x"}) is True
    assert has_undeclared_fields(None, {}) is False


def test_scan_attaches_the_element_path_to_each_finding() -> None:
    found = scan_elements({"arguments.value": "id 1000000008"}, DEFAULT_DETECTORS)
    assert len(found) == 1
    assert isinstance(found[0], ElementFinding)
    assert found[0].element == "arguments.value"
    assert found[0].finding.type == "saudi_national_id"


def test_scan_offsets_are_relative_to_their_own_element() -> None:
    found = scan_elements({"result.variables[1]": "id 1000000008"}, DEFAULT_DETECTORS)
    finding = found[0].finding
    assert "id 1000000008"[finding.start : finding.end] == "1000000008"


def test_clean_elements_yield_no_findings() -> None:
    assert scan_elements({"arguments.key": "DB_URL"}, DEFAULT_DETECTORS) == ()
