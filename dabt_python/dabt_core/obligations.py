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
                start, end = finding.redaction_span
                # last_four exists to keep an identifier's trailing digits
                # legible. Applied to a prose span it would leak the tail of the
                # sentence, so keyword-triggered content is always masked whole.
                strategy = "full" if finding.type == "sensitive_data" else directive.strategy
                obligations.append(RedactionObligation(start, end, finding.type, strategy))
    return tuple(obligations)
