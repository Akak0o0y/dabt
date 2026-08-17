"""NDMO four-level classification with deterministic Principle 4 aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from .detectors.base import Finding
from .schema import ClassificationMapping, ClassificationPolicy, ConfidenceLevel, NdmoLevel


_RANK = {
    NdmoLevel.PUBLIC: 0,
    NdmoLevel.CONFIDENTIAL: 1,
    NdmoLevel.SECRET: 2,
    NdmoLevel.TOP_SECRET: 3,
}

_PII_TYPES = {
    "saudi_national_id",
    "iqama",
    "saudi_iban",
    "saudi_mobile",
    "saudi_commercial_registration",
}


@dataclass(frozen=True)
class ClassificationContext:
    sector: str = "development"
    default_level: str | None = None


@dataclass(frozen=True)
class ClassificationResult:
    level: NdmoLevel
    contributing_levels: tuple[NdmoLevel, ...]
    rationale_en: str
    rationale_ar: str
    confidence_level: ConfidenceLevel
    selected_mapping: ClassificationMapping | None


def _canonical_level(value: str) -> NdmoLevel:
    normalized = value.strip().casefold()
    aliases = {
        "public": NdmoLevel.PUBLIC,
        "confidential": NdmoLevel.CONFIDENTIAL,
        "restricted": NdmoLevel.CONFIDENTIAL,
        "secret": NdmoLevel.SECRET,
        "top secret": NdmoLevel.TOP_SECRET,
    }
    if normalized not in aliases:
        raise ValueError(f"Unknown NDMO level '{value}'")
    return aliases[normalized]


def _sector_default(context: ClassificationContext, policy: ClassificationPolicy | None) -> NdmoLevel:
    if context.default_level:
        return _canonical_level(context.default_level)
    if policy:
        mapped_default = policy.sector_default_for(context.sector)
        if mapped_default:
            return mapped_default
    return NdmoLevel.TOP_SECRET if context.sector.casefold() in {"security", "political"} else NdmoLevel.PUBLIC


def _sector_mapping(context: ClassificationContext, policy: ClassificationPolicy | None) -> ClassificationMapping | None:
    if context.default_level or not policy:
        return None
    return policy.sector_default_mapping_for(context.sector)


def _finding_mapping(finding: Finding, policy: ClassificationPolicy | None) -> ClassificationMapping | None:
    if policy:
        key = f"sensitive_data.{finding.sensitive_category}" if finding.type == "sensitive_data" else finding.type
        mapped = policy.finding_mapping_for(key)
        if mapped is None and finding.type == "sensitive_data":
            mapped = policy.finding_mapping_for("sensitive_data.default")
        if mapped is not None:
            return mapped
    return None


def _finding_level(finding: Finding, policy: ClassificationPolicy | None) -> NdmoLevel:
    mapped = _finding_mapping(finding, policy)
    if mapped is not None:
        return mapped.level
    if finding.type in _PII_TYPES:
        return NdmoLevel.CONFIDENTIAL
    if finding.type == "sensitive_data":
        if finding.sensitive_category in {"health", "biometric", "genetic", "criminal", "credit"}:
            return NdmoLevel.SECRET
        return NdmoLevel.CONFIDENTIAL
    return NdmoLevel.PUBLIC


def classify_findings(
    findings: list[Finding],
    context: ClassificationContext,
    policy: ClassificationPolicy | None = None,
) -> ClassificationResult:
    """Apply NDMO Principle 4: aggregated data receives its maximum level."""
    if not findings:
        default = _sector_default(context, policy)
        default_mapping = _sector_mapping(context, policy)
        return ClassificationResult(
            level=default,
            contributing_levels=(),
            rationale_en=f"No regulated findings detected; applied the {context.sector} sector default.",
            rationale_ar=f"لم تُكتشف نتائج منظمة؛ طُبق الإعداد الافتراضي لقطاع {context.sector}.",
            confidence_level=default_mapping.confidence_level if default_mapping else ConfidenceLevel.VERIFIED,
            selected_mapping=default_mapping,
        )
    levels = tuple(_finding_level(finding, policy) for finding in findings)
    level = max(levels, key=lambda item: _RANK[item])
    mappings = tuple(_finding_mapping(finding, policy) for finding in findings)
    selected_mapping = next(
        (mapping for mapping, mapped_level in zip(mappings, levels, strict=True) if mapping and mapped_level == level),
        None,
    )
    return ClassificationResult(
        level=level,
        contributing_levels=levels,
        rationale_en="Applied NDMO Principle 4: the highest classification across integrated data governs the result.",
        rationale_ar="طُبق المبدأ الرابع لـ NDMO: أعلى تصنيف بين البيانات المجمعة هو الذي يحكم النتيجة.",
        confidence_level=selected_mapping.confidence_level if selected_mapping else ConfidenceLevel.VERIFIED,
        selected_mapping=selected_mapping,
    )
