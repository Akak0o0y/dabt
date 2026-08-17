"""Strict, immutable types for Dabt's legally reviewable compliance map.

Validation occurs when a map is loaded. Evaluation only receives validated types,
preventing a missing confidence or legal-review flag from becoming a runtime fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class SchemaError(ValueError):
    """Raised when a compliance mapping cannot meet Dabt's integrity contract."""


class ConfidenceLevel(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    NEEDS_VERIFICATION = "needs_verification"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    DENY = "DENY"
    REVIEW = "REVIEW"


class NdmoLevel(StrEnum):
    PUBLIC = "Public"
    CONFIDENTIAL = "Confidential"
    SECRET = "Secret"
    TOP_SECRET = "Top Secret"


class Framework(StrEnum):
    PDPL = "PDPL"
    NDMO = "NDMO"
    NCA_ECC_2_2024 = "NCA_ECC_2_2024"
    SAMA_CSF = "SAMA_CSF"


@dataclass(frozen=True)
class Citation:
    article: str
    quote: str
    source_url: str


@dataclass(frozen=True)
class MappedControl:
    framework: str
    control_id: str
    granularity: str
    confidence_level: ConfidenceLevel
    requires_legal_review: bool


@dataclass(frozen=True)
class ClassificationMapping:
    key: str
    level: NdmoLevel
    confidence_level: ConfidenceLevel
    requires_legal_review: bool
    rationale_en: str | None = None
    rationale_ar: str | None = None
    citation: Citation | None = None


@dataclass(frozen=True)
class ClassificationPolicy:
    finding_levels: tuple[ClassificationMapping, ...] = ()
    sector_defaults: tuple[ClassificationMapping, ...] = ()

    def finding_level_for(self, key: str) -> NdmoLevel | None:
        mapping = self.finding_mapping_for(key)
        return mapping.level if mapping else None

    def finding_mapping_for(self, key: str) -> ClassificationMapping | None:
        for mapping in self.finding_levels:
            if mapping.key == key:
                return mapping
        return None

    def sector_default_for(self, sector: str) -> NdmoLevel | None:
        mapping = self.sector_default_mapping_for(sector)
        return mapping.level if mapping else None

    def sector_default_mapping_for(self, sector: str) -> ClassificationMapping | None:
        for mapping in self.sector_defaults:
            if mapping.key.casefold() == sector.casefold():
                return mapping
        return None

    def with_finding_level(self, key: str, level: str) -> "ClassificationPolicy":
        canonical = NdmoLevel(level)
        updated = tuple(
            ClassificationMapping(
                key,
                canonical,
                mapping.confidence_level,
                mapping.requires_legal_review,
                mapping.rationale_en,
                mapping.rationale_ar,
                mapping.citation,
            )
            if mapping.key == key
            else mapping
            for mapping in self.finding_levels
        )
        if all(mapping.key != key for mapping in self.finding_levels):
            updated = (*updated, ClassificationMapping(key, canonical, ConfidenceLevel.INFERRED, True))
        return ClassificationPolicy(updated, self.sector_defaults)


@dataclass(frozen=True)
class RedactionDirective:
    scope: str
    strategy: str
    confidence_level: ConfidenceLevel
    requires_legal_review: bool


@dataclass(frozen=True)
class Rule:
    id: str
    priority: int
    decision: Decision
    framework: str
    citation: Citation
    condition: Mapping[str, Any]
    rationale_en: str
    rationale_ar: str
    mapped_controls: tuple[MappedControl, ...]
    sama_maturity_contribution: int
    confidence_level: ConfidenceLevel
    requires_legal_review: bool
    obligation: RedactionDirective | None = None


@dataclass(frozen=True)
class ComplianceMap:
    version: str
    rules: tuple[Rule, ...]
    classification: ClassificationPolicy = ClassificationPolicy()


_REQUIRED_RULE_FIELDS = (
    "id",
    "priority",
    "decision",
    "framework",
    "citation",
    "condition",
    "rationale_en",
    "rationale_ar",
    "mapped_controls",
    "sama_maturity_contribution",
    "confidence_level",
    "requires_legal_review",
)


def _require(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise SchemaError(f"{label}: missing required field '{key}'")
    return mapping[key]


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{label}: must be a non-empty string")
    return value


def _confidence(value: Any, label: str) -> ConfidenceLevel:
    try:
        return ConfidenceLevel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ConfidenceLevel)
        raise SchemaError(f"{label}: must be one of {allowed}") from exc


def _legal_review(value: Any, label: str) -> bool:
    if value is not True:
        raise SchemaError(f"{label}: must be true")
    return True


def _parse_citation(raw: Any, label: str) -> Citation:
    if not isinstance(raw, Mapping):
        raise SchemaError(f"{label}: citation must be an object")
    return Citation(
        article=_non_empty(_require(raw, "article", label), f"{label}.article"),
        quote=_non_empty(_require(raw, "quote", label), f"{label}.quote"),
        source_url=_non_empty(_require(raw, "source_url", label), f"{label}.source_url"),
    )


def _parse_mapped_control(raw: Mapping[str, Any], rule_id: str, index: int) -> MappedControl:
    label = f"{rule_id}: mapped control {index}"
    framework = _non_empty(_require(raw, "framework", label), f"{label}.framework")
    control_id = _non_empty(_require(raw, "control_id", label), f"{label}.control_id")
    granularity = _non_empty(_require(raw, "granularity", label), f"{label}.granularity")
    confidence = _confidence(
        _require(raw, "confidence_level", label), f"{label}.confidence_level"
    )
    legal_review = _legal_review(
        _require(raw, "requires_legal_review", label),
        f"{label}.requires_legal_review",
    )
    if framework == Framework.NCA_ECC_2_2024 and granularity == "control" and confidence == ConfidenceLevel.VERIFIED:
        raise SchemaError(
            f"{label}: verified NCA ECC leaf-level control claims are prohibited; "
            "use a subdomain mapping or mark it needs_verification"
        )
    return MappedControl(framework, control_id, granularity, confidence, legal_review)


def _parse_rule(raw: Mapping[str, Any]) -> Rule:
    raw_id = raw.get("id", "<unknown-rule>")
    rule_id = _non_empty(raw_id, "rule.id")
    for field in _REQUIRED_RULE_FIELDS:
        _require(raw, field, rule_id)

    citation = _parse_citation(raw["citation"], f"{rule_id}.citation")

    try:
        decision = Decision(raw["decision"])
    except ValueError as exc:
        raise SchemaError(f"{rule_id}: unknown decision '{raw['decision']}'") from exc

    confidence = _confidence(raw["confidence_level"], f"{rule_id}.confidence_level")
    if confidence == ConfidenceLevel.NEEDS_VERIFICATION and decision == Decision.DENY:
        raise SchemaError(
            f"{rule_id}: needs_verification rules may not declare a terminal DENY; use REVIEW"
        )

    raw_controls = raw["mapped_controls"]
    if not isinstance(raw_controls, list):
        raise SchemaError(f"{rule_id}: mapped_controls must be a list")
    controls = tuple(
        _parse_mapped_control(control, rule_id, index)
        for index, control in enumerate(raw_controls, start=1)
    )

    if not isinstance(raw["condition"], Mapping):
        raise SchemaError(f"{rule_id}: condition must be an object")
    if not isinstance(raw["priority"], int):
        raise SchemaError(f"{rule_id}: priority must be an integer")
    if not isinstance(raw["sama_maturity_contribution"], int) or not 0 <= raw["sama_maturity_contribution"] <= 5:
        raise SchemaError(f"{rule_id}: sama_maturity_contribution must be an integer from 0 to 5")

    return Rule(
        id=rule_id,
        priority=raw["priority"],
        decision=decision,
        framework=_non_empty(raw["framework"], f"{rule_id}.framework"),
        citation=citation,
        condition=dict(raw["condition"]),
        rationale_en=_non_empty(raw["rationale_en"], f"{rule_id}.rationale_en"),
        rationale_ar=_non_empty(raw["rationale_ar"], f"{rule_id}.rationale_ar"),
        mapped_controls=controls,
        sama_maturity_contribution=raw["sama_maturity_contribution"],
        confidence_level=confidence,
        requires_legal_review=_legal_review(raw["requires_legal_review"], f"{rule_id}.requires_legal_review"),
        obligation=_parse_obligation(raw.get("obligation"), rule_id),
    )


def _parse_obligation(raw: Any, rule_id: str) -> RedactionDirective | None:
    if raw is None:
        return None
    label = f"{rule_id}.obligation"
    if not isinstance(raw, Mapping):
        raise SchemaError(f"{label}: must be an object")
    scope = _non_empty(_require(raw, "scope", label), f"{label}.scope")
    strategy = _non_empty(_require(raw, "strategy", label), f"{label}.strategy")
    if scope not in {"personal_data", "sensitive_data"}:
        raise SchemaError(f"{label}.scope: must be personal_data or sensitive_data")
    if strategy not in {"full", "last_four"}:
        raise SchemaError(f"{label}.strategy: must be full or last_four")
    return RedactionDirective(
        scope=scope,
        strategy=strategy,
        confidence_level=_confidence(
            _require(raw, "confidence_level", label), f"{label}.confidence_level"
        ),
        requires_legal_review=_legal_review(
            _require(raw, "requires_legal_review", label), f"{label}.requires_legal_review"
        ),
    )


def _parse_ndmo_level(value: Any, label: str) -> NdmoLevel:
    aliases = {"Restricted": NdmoLevel.CONFIDENTIAL, "restricted": NdmoLevel.CONFIDENTIAL}
    if value in aliases:
        return aliases[value]
    try:
        return NdmoLevel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in NdmoLevel)
        raise SchemaError(f"{label}: must be one of {allowed}") from exc


def _parse_classification_entries(raw: Any, section: str) -> tuple[ClassificationMapping, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Mapping):
        raise SchemaError(f"classification.{section}: must be an object")
    entries: list[ClassificationMapping] = []
    for key, data in raw.items():
        label = f"classification.{section}.{key}"
        if not isinstance(data, Mapping):
            raise SchemaError(f"{label}: must be an object")
        confidence = _confidence(
            _require(data, "confidence_level", label), f"{label}.confidence_level"
        )
        rationale_en: str | None = None
        rationale_ar: str | None = None
        citation: Citation | None = None
        if confidence == ConfidenceLevel.INFERRED:
            rationale_en = _non_empty(
                _require(data, "rationale_en", label), f"{label}.rationale_en"
            )
            rationale_ar = _non_empty(
                _require(data, "rationale_ar", label), f"{label}.rationale_ar"
            )
            citation = _parse_citation(
                _require(data, "citation", label), f"{label}.citation"
            )
        entries.append(
            ClassificationMapping(
                key=_non_empty(str(key), f"{label}.key"),
                level=_parse_ndmo_level(_require(data, "level", label), f"{label}.level"),
                confidence_level=confidence,
                requires_legal_review=_legal_review(
                    _require(data, "requires_legal_review", label),
                    f"{label}.requires_legal_review",
                ),
                rationale_en=rationale_en,
                rationale_ar=rationale_ar,
                citation=citation,
            )
        )
    return tuple(entries)


def _parse_classification(raw: Any) -> ClassificationPolicy:
    if raw is None:
        return ClassificationPolicy()
    if not isinstance(raw, Mapping):
        raise SchemaError("classification: must be an object")
    return ClassificationPolicy(
        finding_levels=_parse_classification_entries(raw.get("finding_levels"), "finding_levels"),
        sector_defaults=_parse_classification_entries(raw.get("sector_defaults"), "sector_defaults"),
    )


def validate_map_payload(raw: Mapping[str, Any]) -> ComplianceMap:
    """Validate an untrusted YAML payload and return an immutable ComplianceMap."""
    if not isinstance(raw, Mapping):
        raise SchemaError("compliance map: expected an object")
    version = _non_empty(_require(raw, "version", "compliance map"), "compliance map.version")
    raw_rules = _require(raw, "rules", "compliance map")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise SchemaError("compliance map.rules: must be a non-empty list")

    rules = tuple(_parse_rule(rule) for rule in raw_rules if isinstance(rule, Mapping))
    if len(rules) != len(raw_rules):
        raise SchemaError("compliance map.rules: every entry must be an object")
    ids = [rule.id for rule in rules]
    if len(ids) != len(set(ids)):
        raise SchemaError("compliance map.rules: duplicate rule ids are not permitted")
    return ComplianceMap(
        version=version,
        rules=tuple(sorted(rules, key=lambda rule: rule.priority)),
        classification=_parse_classification(raw.get("classification")),
    )
