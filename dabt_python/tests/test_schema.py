from __future__ import annotations

import pytest

from dabt_core.schema import SchemaError, validate_map_payload


def base_rule() -> dict:
    return {
        "id": "TEST-RULE",
        "priority": 1,
        "decision": "ALLOW",
        "framework": "PDPL",
        "citation": {
            "article": "Article 1",
            "quote": "Verbatim source text.",
            "source_url": "https://example.test/source",
        },
        "condition": {"always": True},
        "rationale_en": "English rationale.",
        "rationale_ar": "مبرر عربي.",
        "mapped_controls": [
            {
                "framework": "NCA_ECC_2_2024",
                "control_id": "2-7",
                "granularity": "subdomain",
                "confidence_level": "needs_verification",
                "requires_legal_review": True,
            }
        ],
        "sama_maturity_contribution": 3,
        "confidence_level": "verified",
        "requires_legal_review": True,
    }


def payload_with(rule: dict) -> dict:
    return {"version": "0.1", "rules": [rule]}


def test_rule_requires_confidence_level() -> None:
    rule = base_rule()
    rule.pop("confidence_level")
    with pytest.raises(SchemaError, match="TEST-RULE.*confidence_level"):
        validate_map_payload(payload_with(rule))


def test_rule_requires_legal_review_true() -> None:
    rule = base_rule()
    rule["requires_legal_review"] = False
    with pytest.raises(SchemaError, match="TEST-RULE.*requires_legal_review"):
        validate_map_payload(payload_with(rule))


def test_mapped_control_requires_integrity_fields() -> None:
    rule = base_rule()
    rule["mapped_controls"][0].pop("requires_legal_review")
    with pytest.raises(SchemaError, match="TEST-RULE.*mapped control.*requires_legal_review"):
        validate_map_payload(payload_with(rule))


def test_rule_requires_both_languages() -> None:
    rule = base_rule()
    rule.pop("rationale_ar")
    with pytest.raises(SchemaError, match="TEST-RULE.*rationale_ar"):
        validate_map_payload(payload_with(rule))


def test_citation_quote_must_be_nonempty() -> None:
    rule = base_rule()
    rule["citation"]["quote"] = ""
    with pytest.raises(SchemaError, match="TEST-RULE.*citation.quote"):
        validate_map_payload(payload_with(rule))


def test_valid_rule_is_accepted() -> None:
    compliance_map = validate_map_payload(payload_with(base_rule()))
    assert compliance_map.rules[0].id == "TEST-RULE"
    assert compliance_map.rules[0].requires_legal_review is True
