from pathlib import Path

from dabt_core.loader import load_compliance_map
from dabt_core.rules import evaluate_policy
from dabt_core.schema import ConfidenceLevel, Decision

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def clean_action_context() -> dict:
    return {
        "surface": "action",
        "leg": "request",
        "tool_manifested": True,
        "tool_confidence": "verified",
        "contains_personal_data": False,
        "contains_sensitive_data": False,
        "response_declared_credential": False,
        "undeclared_response_fields": False,
        "persists_data": False,
        "deployment_region_in_kingdom": True,
        "classification": "Public",
        "sensitive_categories": frozenset(),
    }


def test_manifested_action_with_no_findings_allows() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = evaluate_policy(compliance_map, clean_action_context())
    assert decision.decision == Decision.ALLOW
    assert decision.rule.id == "ACTION-DEFAULT-ALLOW-NO-FINDING"


def test_public_retrieval_allow_does_not_fire_on_actions() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = evaluate_policy(compliance_map, clean_action_context())
    assert "NDMO-PUBLIC-ALLOW" not in {rule.id for rule in decision.fired_rules}


def test_unverified_tool_does_not_reach_allow() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["tool_confidence"] = "needs_verification"
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW


def test_unmanifested_tool_does_not_reach_allow() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["tool_manifested"] = False
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW


def test_undeclared_response_fields_do_not_reach_allow() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["undeclared_response_fields"] = True
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW


def test_provisioning_outside_the_kingdom_reviews() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["persists_data"] = True
    context["deployment_region_in_kingdom"] = False
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW
    assert decision.rule.id == "PDPL-ART29-2C-INFERRED-RESIDENCY"


def test_residency_rule_cannot_terminally_deny() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    rule = next(r for r in compliance_map.rules if r.id == "PDPL-ART29-2C-INFERRED-RESIDENCY")
    assert rule.confidence_level == ConfidenceLevel.NEEDS_VERIFICATION
    assert rule.decision != Decision.DENY


def test_declared_credential_does_not_block_the_request_leg() -> None:
    # The write must be able to proceed; only its disclosure is gated.
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["response_declared_credential"] = True
    assert evaluate_policy(compliance_map, context).decision == Decision.ALLOW


def test_declared_credential_response_reviews_on_the_response_leg() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["leg"] = "response"
    context["response_declared_credential"] = True
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW
    assert decision.rule.id == "NCA-ECC-CREDENTIAL-DISCLOSURE"
