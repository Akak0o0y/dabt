from dataclasses import replace

from dabt_core.detectors.base import Finding
from dabt_core.engine import PolicyDecision
from dabt_core.loader import load_compliance_map
from dabt_core.obligations import resolve_obligations
from dabt_core.schema import Decision


def personal_finding() -> Finding:
    return Finding("saudi_national_id", "1000000008", "1000000008", 0, 10, "checksum_verified", "verified", True)


def test_fired_rule_directive_drives_redaction_strategy() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    cross_border = next(rule for rule in compliance_map.rules if rule.id == "PDPL-ART29-2C-CROSSBORDER-MINIMISATION")
    disclosure = next(rule for rule in compliance_map.rules if rule.id == "PDPL-ART15-5-ANONYMISED-DISCLOSURE")

    cross_border_obligations = resolve_obligations(
        PolicyDecision(Decision.ALLOW_WITH_REDACTION, cross_border, (cross_border,)), (personal_finding(),)
    )
    disclosure_obligations = resolve_obligations(
        PolicyDecision(Decision.ALLOW_WITH_REDACTION, disclosure, (disclosure,)), (personal_finding(),)
    )

    assert cross_border_obligations[0].strategy == "full"
    assert disclosure_obligations[0].strategy == "last_four"


def test_allow_with_redaction_without_a_fired_rule_directive_has_no_obligation() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    public = next(rule for rule in compliance_map.rules if rule.id == "NDMO-PUBLIC-ALLOW")
    synthetic = replace(public, decision=Decision.ALLOW_WITH_REDACTION, obligation=None)
    assert resolve_obligations(
        PolicyDecision(Decision.ALLOW_WITH_REDACTION, synthetic, (synthetic,)), (personal_finding(),)
    ) == ()
