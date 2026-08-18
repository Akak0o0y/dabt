from pathlib import Path

from dabt_core import rules
from dabt_core.loader import load_compliance_map
from dabt_core.schema import Decision

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def test_rules_module_exposes_shared_matcher_and_evaluator() -> None:
    assert callable(rules.rule_matches)
    assert callable(rules.evaluate_policy)


def test_engine_and_rules_expose_the_same_matcher() -> None:
    from dabt_core import engine

    assert engine.rule_matches is rules.rule_matches
    assert engine.PolicyDecision is rules.PolicyDecision


def test_evaluate_policy_returns_review_when_no_rule_matches() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = rules.evaluate_policy(compliance_map, {"classification": "__nothing_matches__"})
    assert decision.decision == Decision.REVIEW
    assert decision.rule is None
    assert decision.fired_rules == ()
