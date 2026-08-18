from dataclasses import replace

from dabt_core.detectors.base import Finding
from dabt_core.detectors.sensitive import SensitiveDataDetector
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


def sensitive_finding() -> Finding:
    text = "Note. The applicant provided a fingerprint template today. Tail."
    return SensitiveDataDetector().detect(text)[0]


def test_sensitive_obligation_masks_the_content_span_in_full() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    partial = next(rule for rule in compliance_map.rules if rule.id == "PDPL-ART15-5-ANONYMISED-DISCLOSURE")
    assert partial.obligation is not None and partial.obligation.strategy == "last_four"

    finding = sensitive_finding()
    obligation = resolve_obligations(
        PolicyDecision(Decision.ALLOW_WITH_REDACTION, partial, (partial,)), (finding,)
    )[0]

    # The rule asks for partial masking, which is meaningful only for an
    # identifier. Prose content is masked whole over the wider content span.
    assert obligation.strategy == "full"
    assert (obligation.start, obligation.end) == finding.redaction_span
    assert (obligation.start, obligation.end) != (finding.start, finding.end)
