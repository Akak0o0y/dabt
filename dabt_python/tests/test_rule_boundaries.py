from __future__ import annotations

from pathlib import Path

import pytest

from dabt_core.engine import rule_matches
from dabt_core.loader import load_compliance_map


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"

_MATCHING_CONTEXTS = {
    "NDMO-TOP-SECRET-DENY": {"classification": "Top Secret"},
    "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST": {"lawful_basis": "legitimate_interest", "contains_sensitive_data": True},
    "PDPL-ART15-6-SENSITIVE-DISCLOSURE": {"event_type": "disclosure", "lawful_basis": "legitimate_interest", "contains_sensitive_data": True},
    "PDPL-ART23-HEALTH-DATA-RESTRICTION": {"contains_sensitive_category": "health"},
    "PDPL-ART24-CREDIT-DATA-CONSENT": {"contains_sensitive_category": "credit"},
    "PDPL-ART29-2C-CROSSBORDER-MINIMISATION": {"cross_border": True, "contains_personal_data": True},
    "PDPL-ART15-5-ANONYMISED-DISCLOSURE": {"event_type": "disclosure", "contains_personal_data": True},
    "PDPL-ART11-3-MINIMISATION": {"contains_personal_data": True, "requires_minimisation": True},
    "NDMO-SECRET-RESTRICTED-ACCESS": {"classification": "Secret", "agent_authorised": True},
    "NDMO-PUBLIC-ALLOW": {"classification": "Public"},
}


@pytest.mark.parametrize("rule_id", list(_MATCHING_CONTEXTS))
def test_every_rule_has_a_firing_condition(rule_id: str) -> None:
    rule = next(rule for rule in load_compliance_map(MAP_PATH).rules if rule.id == rule_id)
    assert rule_matches(rule, _MATCHING_CONTEXTS[rule_id]) is True


@pytest.mark.parametrize("rule_id", list(_MATCHING_CONTEXTS))
def test_every_rule_has_a_non_firing_boundary(rule_id: str) -> None:
    rule = next(rule for rule in load_compliance_map(MAP_PATH).rules if rule.id == rule_id)
    context = dict(_MATCHING_CONTEXTS[rule_id])
    key = next(iter(rule.condition))
    context[key] = (not context[key]) if isinstance(context[key], bool) else "__boundary_non_match__"
    assert rule_matches(rule, context) is False

