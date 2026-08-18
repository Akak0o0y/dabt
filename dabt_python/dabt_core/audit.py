"""Bilingual, non-authoritative audit transparency for Dabt decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


LEGAL_REVIEW_DISCLAIMER_EN = (
    "This engineering output requires qualified Saudi legal or compliance review before regulatory reliance."
)
LEGAL_REVIEW_DISCLAIMER_AR = (
    "يتطلب هذا المخرج الهندسي مراجعة قانونية أو مراجعة امتثال مؤهلة في المملكة العربية السعودية قبل الاعتماد التنظيمي."
)


@dataclass(frozen=True)
class AuditRecord:
    decision: str
    decision_rule_id: str | None
    classification: str
    timestamp: str
    summary_en: str
    summary_ar: str
    legal_review_disclaimer_en: str
    legal_review_disclaimer_ar: str
    fired_rules: tuple[dict[str, Any], ...]
    mapped_controls: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "decision_rule_id": self.decision_rule_id,
            "classification": self.classification,
            "timestamp": self.timestamp,
            "summary_en": self.summary_en,
            "summary_ar": self.summary_ar,
            "legal_review_disclaimer_en": self.legal_review_disclaimer_en,
            "legal_review_disclaimer_ar": self.legal_review_disclaimer_ar,
            "fired_rules": list(self.fired_rules),
            "mapped_controls": list(self.mapped_controls),
        }


def _controls(fired_rules: Iterable[Any]) -> tuple[dict[str, str], ...]:
    controls: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in fired_rules:
        for mapped in rule.mapped_controls:
            identity = (str(mapped.framework), mapped.control_id, mapped.granularity)
            if identity in seen:
                continue
            seen.add(identity)
            controls.append(
                {
                    "framework": str(mapped.framework),
                    "control_id": mapped.control_id,
                    "granularity": mapped.granularity,
                    "confidence_level": str(mapped.confidence_level),
                    "requires_legal_review": str(mapped.requires_legal_review).lower(),
                }
            )
    return tuple(controls)


def _subject(request: Any, surface: str) -> tuple[str, str]:
    """Name what was evaluated, in both languages.

    One engine serves two surfaces, so the record has to say which one it is
    describing. A record that calls a tool call a retrieval misstates the event
    it exists to evidence.
    """
    if surface != "action":
        return "the retrieval", "طلب الاسترجاع"
    tool = getattr(request, "tool", None)
    if not tool:
        return "the tool call", "استدعاء الأداة"
    return f"the tool call '{tool}'", f"استدعاء الأداة «{tool}»"


def build_audit_record(
    request: Any,
    classification: str,
    policy_decision: Any,
    obligations: Iterable[Any],
    timestamp: str,
    surface: str = "retrieval",
) -> AuditRecord:
    """Build one bilingual record without exposing raw document content."""
    rule = policy_decision.rule
    subject_en, subject_ar = _subject(request, surface)
    fired_rules = tuple(
        {
            "id": fired.id,
            "framework": fired.framework,
            "article": fired.citation.article,
            "confidence_level": str(fired.confidence_level),
            "requires_legal_review": fired.requires_legal_review,
            "rationale_en": fired.rationale_en,
            "rationale_ar": fired.rationale_ar,
        }
        for fired in policy_decision.fired_rules
    )
    rule_name = rule.id if rule else "no matching map rule"
    # Counted once: `obligations` may be a generator, and consuming it twice
    # would report zero in the second language.
    obligation_count = len(tuple(obligations))
    return AuditRecord(
        decision=str(policy_decision.decision),
        decision_rule_id=rule.id if rule else None,
        classification=classification,
        timestamp=timestamp,
        summary_en=(
            f"Dabt evaluated {subject_en} as {policy_decision.decision}; decision basis: {rule_name}. "
            f"{obligation_count} redaction obligation(s) were resolved."
        ),
        summary_ar=(
            f"قيّمت منصة ضبط {subject_ar} بالنتيجة {policy_decision.decision}؛ أساس القرار: {rule_name}. "
            f"وتم تحديد {obligation_count} من التزامات الحجب."
        ),
        legal_review_disclaimer_en=LEGAL_REVIEW_DISCLAIMER_EN,
        legal_review_disclaimer_ar=LEGAL_REVIEW_DISCLAIMER_AR,
        fired_rules=fired_rules,
        mapped_controls=_controls(policy_decision.fired_rules),
    )
