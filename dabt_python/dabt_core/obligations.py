"""Deterministic obligations resolved after a policy decision."""

from __future__ import annotations

from dataclasses import dataclass

from .detectors.base import Finding
from .schema import Decision


@dataclass(frozen=True)
class RedactionObligation:
    start: int
    end: int
    category: str
    strategy: str


def resolve_obligations(policy_decision: object, findings: tuple[Finding, ...]) -> tuple[RedactionObligation, ...]:
    """Resolve spans from the directives on the rules that actually fired."""
    if getattr(policy_decision, "decision") != Decision.ALLOW_WITH_REDACTION:
        return ()
    obligations: list[RedactionObligation] = []
    for rule in getattr(policy_decision, "fired_rules"):
        directive = rule.obligation
        if directive is None:
            continue
        for finding in findings:
            applies = directive.scope == "personal_data" and finding.is_personal_data
            applies = applies or (directive.scope == "sensitive_data" and finding.type == "sensitive_data")
            if applies:
                obligations.append(
                    RedactionObligation(finding.start, finding.end, finding.type, directive.strategy)
                )
    return tuple(obligations)
