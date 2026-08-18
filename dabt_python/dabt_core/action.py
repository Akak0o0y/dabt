"""The Agent Action Gate: policy evaluation for MCP tool calls.

The retrieval gate evaluates one document. An action gate evaluates a set of
named values — a tool call's arguments on the request leg, its declared response
fields on the response leg. Detection, classification, redaction and audit are
the retrieval gate's, unchanged; only the shape of the payload differs, so a
finding carries the element it came from and offsets relative to that element.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .audit import AuditRecord, build_audit_record
from .classifier import ClassificationContext, ClassificationResult, classify_findings
from .detectors import DEFAULT_DETECTORS
from .detectors.base import Detector, Finding
from .manifest import ToolManifest, ToolSpec
from .rules import PolicyDecision, evaluate_policy
from .schema import ComplianceMap, Decision, Rule


@dataclass(frozen=True)
class ElementFinding:
    """One detection result, tagged with the element of the call it came from."""

    element: str
    finding: Finding


@dataclass(frozen=True)
class ElementObligation:
    element: str
    start: int
    end: int
    strategy: str


@dataclass(frozen=True)
class ActionRequest:
    server_id: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


@dataclass(frozen=True)
class ActionResultRequest:
    server_id: str
    tool: str
    result: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


def flatten_arguments(spec: ToolSpec | None, arguments: Mapping[str, Any]) -> dict[str, str]:
    """Every argument value is inspectable; the manifest governs masking, not scanning."""
    flattened: dict[str, str] = {}
    for name, value in arguments.items():
        if value is None:
            continue
        flattened[f"arguments.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def flatten_result(spec: ToolSpec | None, result: Mapping[str, Any]) -> dict[str, str]:
    """Only manifest-declared response fields marked for inspection are scanned."""
    if spec is None:
        return {}
    flattened: dict[str, str] = {}
    for name, value in result.items():
        declared = spec.return_field(name)
        if declared is None or not declared.inspect_content or value is None:
            continue
        if declared.collection and isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if item is None:
                    continue
                flattened[f"result.{name}[{index}]"] = item if isinstance(item, str) else str(item)
            continue
        flattened[f"result.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def has_undeclared_fields(spec: ToolSpec | None, result: Mapping[str, Any]) -> bool:
    """A response field the manifest never described cannot be reasoned about.

    Spec limitation 2: such a field is not inspected, so it must not be able to
    reach ALLOW. Without this the gate would permit a response purely because it
    failed to look at it.
    """
    if spec is None:
        return bool(result)
    return any(spec.return_field(name) is None for name in result)


def scan_elements(
    values: Mapping[str, str], detectors: Iterable[Detector]
) -> tuple[ElementFinding, ...]:
    """Run every detector over each element independently, preserving local offsets."""
    detectors = tuple(detectors)
    found: list[ElementFinding] = []
    for element in sorted(values):
        text = values[element]
        for detector in detectors:
            for finding in detector.detect(text):
                found.append(ElementFinding(element, finding))
    return tuple(
        sorted(
            found,
            key=lambda item: (item.element, item.finding.start, item.finding.end, item.finding.type),
        )
    )


@dataclass(frozen=True)
class ActionResult:
    decision: Decision
    decision_rule_id: str | None
    classification: str
    classification_evidence: dict[str, object]
    findings: tuple[ElementFinding, ...]
    fired_rules: tuple[Rule, ...]
    audit: AuditRecord
    manifest_version: str | None
    obligations: tuple[ElementObligation, ...] = ()
    released_arguments: dict[str, Any] | None = None
    released_result: dict[str, Any] | None = None
    rewritten: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": str(self.decision),
            "decision_rule_id": self.decision_rule_id,
            "classification": self.classification,
            "classification_evidence": self.classification_evidence,
            "findings": [
                {
                    "element": item.element,
                    "type": item.finding.type,
                    "start": item.finding.start,
                    "end": item.finding.end,
                    "confidence_tier": item.finding.confidence_tier,
                    "confidence_level": item.finding.confidence_level,
                    "checksum_result": item.finding.checksum_result,
                    "sensitive_category": item.finding.sensitive_category,
                }
                for item in self.findings
            ],
            "fired_rules": [rule.id for rule in self.fired_rules],
            "obligations": [
                {"element": item.element, "start": item.start, "end": item.end, "strategy": item.strategy}
                for item in self.obligations
            ],
            "released_arguments": self.released_arguments,
            "released_result": self.released_result,
            "rewritten": self.rewritten,
            "audit": self.audit.to_dict(),
            "manifest_version": self.manifest_version,
        }


class ActionEngine:
    """Pure action evaluator: map, manifests and detectors are injected; no I/O here."""

    def __init__(
        self,
        compliance_map: ComplianceMap,
        manifests: Mapping[str, ToolManifest],
        detectors: Iterable[Detector] = DEFAULT_DETECTORS,
    ) -> None:
        self._map = compliance_map
        self._manifests = dict(manifests)
        self._detectors = tuple(detectors)

    def _spec(self, server_id: str, tool: str) -> tuple[ToolManifest | None, ToolSpec | None]:
        manifest = self._manifests.get(server_id)
        return manifest, (manifest.tool(tool) if manifest else None)

    def build_context(
        self,
        spec: ToolSpec | None,
        request: Any,
        findings: tuple[ElementFinding, ...],
        classification: str,
        leg: str,
        undeclared_response_fields: bool,
    ) -> dict[str, object]:
        sensitive_categories = frozenset(
            item.finding.sensitive_category for item in findings if item.finding.sensitive_category
        )
        region_in_kingdom = True
        if spec is not None:
            for parameter in spec.parameters:
                if parameter.role != "deployment_region":
                    continue
                value = getattr(request, "arguments", {}).get(parameter.name)
                if value is not None:
                    region_in_kingdom = self._map.region_in_kingdom(str(value))
        return {
            "surface": "action",
            "leg": leg,
            "undeclared_response_fields": undeclared_response_fields,
            "classification": classification,
            "lawful_basis": request.lawful_basis,
            "event_type": "action",
            "agent_authorised": request.agent_authorised,
            "requires_minimisation": request.requires_minimisation,
            "contains_personal_data": any(item.finding.is_personal_data for item in findings),
            "contains_sensitive_data": bool(sensitive_categories),
            "sensitive_categories": sensitive_categories,
            "tool_manifested": spec is not None,
            "tool_confidence": str(spec.confidence_level) if spec else "needs_verification",
            "operation": spec.operation if spec else None,
            "resource_type": spec.resource_type if spec else None,
            "persists_data": spec.persists_data if spec else False,
            "deployment_region_in_kingdom": region_in_kingdom,
            "response_declared_credential": spec.declares_sensitive_response if spec else False,
        }

    def _finish(
        self,
        request: Any,
        spec: ToolSpec | None,
        manifest: ToolManifest | None,
        findings: tuple[ElementFinding, ...],
        timestamp: str,
        leg: str,
        undeclared_response_fields: bool = False,
    ) -> tuple[ActionResult, PolicyDecision]:
        classification: ClassificationResult = classify_findings(
            [item.finding for item in findings],
            ClassificationContext(sector=request.sector),
            self._map.classification,
        )
        context = self.build_context(
            spec, request, findings, classification.level.value, leg, undeclared_response_fields
        )
        policy = evaluate_policy(self._map, context)
        audit = build_audit_record(request, classification.level.value, policy, (), timestamp)
        selected = classification.selected_mapping
        evidence: dict[str, object] = {
            "mapping_key": selected.key if selected else None,
            "confidence_level": str(classification.confidence_level),
            "requires_legal_review": selected.requires_legal_review if selected else True,
            "rationale_en": selected.rationale_en if selected else classification.rationale_en,
            "rationale_ar": selected.rationale_ar if selected else classification.rationale_ar,
            "citation": (
                {
                    "article": selected.citation.article,
                    "quote": selected.citation.quote,
                    "source_url": selected.citation.source_url,
                }
                if selected and selected.citation
                else None
            ),
        }
        result = ActionResult(
            decision=policy.decision,
            decision_rule_id=policy.rule.id if policy.rule else None,
            classification=classification.level.value,
            classification_evidence=evidence,
            findings=findings,
            fired_rules=policy.fired_rules,
            audit=audit,
            manifest_version=manifest.version if manifest else None,
        )
        return result, policy

    def evaluate(self, request: ActionRequest, timestamp: str) -> ActionResult:
        """Request leg: gate the act itself."""
        manifest, spec = self._spec(request.server_id, request.tool)
        findings = scan_elements(flatten_arguments(spec, request.arguments), self._detectors)
        result, _ = self._finish(request, spec, manifest, findings, timestamp, "request")
        return result

    def evaluate_result(self, request: ActionResultRequest, timestamp: str) -> ActionResult:
        """Response leg: gate the disclosure of what the act returned."""
        manifest, spec = self._spec(request.server_id, request.tool)
        findings = scan_elements(flatten_result(spec, request.result), self._detectors)
        result, _ = self._finish(
            request,
            spec,
            manifest,
            findings,
            timestamp,
            "response",
            has_undeclared_fields(spec, request.result),
        )
        return result
