"""Dabt's deterministic six-stage retrieval policy evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .audit import AuditRecord, build_audit_record
from .classifier import ClassificationContext, ClassificationResult, classify_findings
from .detectors import DEFAULT_DETECTORS
from .detectors.base import Detector, Finding
from .obligations import RedactionObligation, resolve_obligations
from .redactor import apply_redactions
from .rules import PolicyDecision, evaluate_policy, rule_matches
from .schema import ComplianceMap, Decision, Rule


@dataclass(frozen=True)
class EngineRequest:
    document: str
    agent_id: str = "demo-agent"
    purpose: str = "retrieval"
    lawful_basis: str = "consent"
    cross_border: bool = False
    sector: str = "development"
    event_type: str = "disclosure"
    agent_authorised: bool = True
    requires_minimisation: bool = True


@dataclass(frozen=True)
class EngineResult:
    decision: Decision
    decision_rule_id: str | None
    classification: str
    classification_evidence: dict[str, object]
    findings: tuple[Finding, ...]
    fired_rules: tuple[Rule, ...]
    obligations: tuple[RedactionObligation, ...]
    redacted_document: str
    audit: AuditRecord

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": str(self.decision),
            "decision_rule_id": self.decision_rule_id,
            "classification": self.classification,
            "classification_evidence": self.classification_evidence,
            "findings": [
                {
                    "type": item.type,
                    "start": item.start,
                    "end": item.end,
                    "value": item.value,
                    "normalized_value": item.normalized_value,
                    "confidence_tier": item.confidence_tier,
                    "confidence_level": item.confidence_level,
                    "checksum_result": item.checksum_result,
                    "sensitive_category": item.sensitive_category,
                    "redaction_start": item.redaction_span[0],
                    "redaction_end": item.redaction_span[1],
                }
                for item in self.findings
            ],
            "fired_rules": [rule.id for rule in self.fired_rules],
            "obligations": [
                {"start": item.start, "end": item.end, "category": item.category, "strategy": item.strategy}
                for item in self.obligations
            ],
            "redacted_document": self.redacted_document,
            "audit": self.audit.to_dict(),
        }


class PolicyEngine:
    """Pure policy evaluator: map and detectors are injected; no I/O occurs here."""

    def __init__(self, compliance_map: ComplianceMap, detectors: Iterable[Detector] = DEFAULT_DETECTORS) -> None:
        self._map = compliance_map
        self._detectors = tuple(detectors)

    def evaluate(
        self,
        request: EngineRequest,
        timestamp: str,
        trace: list[str] | None = None,
    ) -> EngineResult:
        def stage(name: str) -> None:
            if trace is not None:
                trace.append(name)

        stage("detection")
        findings = tuple(
            sorted(
                (finding for detector in self._detectors for finding in detector.detect(request.document)),
                key=lambda finding: (finding.start, finding.end, finding.type),
            )
        )

        stage("classification")
        classification: ClassificationResult = classify_findings(
            list(findings),
            ClassificationContext(sector=request.sector),
            self._map.classification,
        )

        stage("policy_evaluation")
        sensitive_categories = frozenset(
            finding.sensitive_category for finding in findings if finding.sensitive_category
        )
        context: dict[str, object] = {
            "classification": classification.level.value,
            "lawful_basis": request.lawful_basis,
            "event_type": request.event_type,
            "cross_border": request.cross_border,
            "agent_authorised": request.agent_authorised,
            "requires_minimisation": request.requires_minimisation,
            "contains_personal_data": any(finding.is_personal_data for finding in findings),
            "contains_sensitive_data": bool(sensitive_categories),
            "sensitive_categories": sensitive_categories,
        }
        policy = evaluate_policy(self._map, context)

        stage("obligation_resolution")
        obligations = resolve_obligations(policy, findings)

        stage("redaction")
        if policy.decision in {Decision.DENY, Decision.REVIEW}:
            redacted_document = "[DENIED — no payload released | مرفوض — لم يتم الإفراج عن أي حمولة]"
        else:
            redacted_document = apply_redactions(request.document, obligations)

        stage("audit_logging")
        audit = build_audit_record(request, classification.level.value, policy, obligations, timestamp)
        selected_mapping = classification.selected_mapping
        classification_evidence: dict[str, object] = {
            "mapping_key": selected_mapping.key if selected_mapping else None,
            "confidence_level": str(classification.confidence_level),
            "requires_legal_review": selected_mapping.requires_legal_review if selected_mapping else True,
            "rationale_en": selected_mapping.rationale_en if selected_mapping else classification.rationale_en,
            "rationale_ar": selected_mapping.rationale_ar if selected_mapping else classification.rationale_ar,
            "citation": (
                {
                    "article": selected_mapping.citation.article,
                    "quote": selected_mapping.citation.quote,
                    "source_url": selected_mapping.citation.source_url,
                }
                if selected_mapping and selected_mapping.citation
                else None
            ),
        }

        return EngineResult(
            decision=policy.decision,
            decision_rule_id=policy.rule.id if policy.rule else None,
            classification=classification.level.value,
            classification_evidence=classification_evidence,
            findings=findings,
            fired_rules=policy.fired_rules,
            obligations=obligations,
            redacted_document=redacted_document,
            audit=audit,
        )
