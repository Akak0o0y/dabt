"""Policy matching and decision semantics shared by every enforcement surface.

Both the retrieval gate and the action gate evaluate the same compliance map.
They must agree on what a condition means and on how an unverified rule
degrades, so that logic lives here once rather than in each engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .schema import ComplianceMap, ConfidenceLevel, Decision, Rule


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    rule: Rule | None
    fired_rules: tuple[Rule, ...]


def rule_matches(rule: Rule, context: Mapping[str, object]) -> bool:
    """Match declared map conditions exactly; special category matching is set-aware."""
    for key, expected in rule.condition.items():
        if key == "contains_sensitive_category":
            categories = context.get("sensitive_categories", context.get("contains_sensitive_category", frozenset()))
            if isinstance(categories, str):
                categories = frozenset({categories})
            if expected not in categories:
                return False
            continue
        if context.get(key) != expected:
            return False
    return True


def evaluate_policy(compliance_map: ComplianceMap, context: Mapping[str, object]) -> PolicyDecision:
    """First matching rule by priority wins; an unverified rule may not terminally deny."""
    fired_rules = tuple(rule for rule in compliance_map.rules if rule_matches(rule, context))
    if not fired_rules:
        return PolicyDecision(Decision.REVIEW, None, ())
    winner = fired_rules[0]
    decision = winner.decision
    # Defence in depth: a directly constructed invalid in-memory map still cannot deny on unverified content.
    if decision == Decision.DENY and winner.confidence_level == ConfidenceLevel.NEEDS_VERIFICATION:
        decision = Decision.REVIEW
    return PolicyDecision(decision, winner, fired_rules)
