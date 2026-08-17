from pathlib import Path

from dabt_core.classifier import ClassificationContext, classify_findings
from dabt_core.detectors.base import Finding
from dabt_core.loader import load_compliance_map
from dabt_core.schema import NdmoLevel


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def finding(kind: str, *, sensitive_category: str | None = None) -> Finding:
    return Finding(
        type=kind,
        value="sample",
        normalized_value="sample",
        start=0,
        end=6,
        confidence_tier="format_detected",
        confidence_level="verified",
        checksum_result=None,
        sensitive_category=sensitive_category,
    )


def test_pii_finding_classifies_confidential() -> None:
    result = classify_findings([finding("saudi_national_id")], ClassificationContext())
    assert result.level == NdmoLevel.CONFIDENTIAL


def test_principle_4_aggregation_takes_maximum() -> None:
    result = classify_findings(
        [finding("saudi_mobile"), finding("sensitive_data", sensitive_category="health")],
        ClassificationContext(),
    )
    assert result.level == NdmoLevel.SECRET


def test_principle_4_is_not_average_or_first_finding() -> None:
    result = classify_findings(
        [finding("public_indicator"), finding("saudi_iban")], ClassificationContext(),
    )
    assert result.level == NdmoLevel.CONFIDENTIAL


def test_sector_default_applies_when_no_findings() -> None:
    result = classify_findings([], ClassificationContext(default_level="Confidential"))
    assert result.level == NdmoLevel.CONFIDENTIAL


def test_security_sector_defaults_to_top_secret() -> None:
    result = classify_findings([], ClassificationContext(sector="security"))
    assert result.level == NdmoLevel.TOP_SECRET


def test_restricted_is_accepted_as_confidential_synonym() -> None:
    result = classify_findings([], ClassificationContext(default_level="Restricted"))
    assert result.level == NdmoLevel.CONFIDENTIAL


def test_canonical_output_label_is_confidential_never_restricted() -> None:
    result = classify_findings([], ClassificationContext(default_level="Restricted"))
    assert result.level.value == "Confidential"


def test_classifier_uses_validated_compliance_map_configuration() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    result = classify_findings(
        [finding("saudi_national_id")],
        ClassificationContext(),
        compliance_map.classification,
    )
    assert result.level == NdmoLevel.CONFIDENTIAL

    overridden_policy = compliance_map.classification.with_finding_level(
        "saudi_national_id", "Top Secret"
    )
    overridden = classify_findings(
        [finding("saudi_national_id")], ClassificationContext(), overridden_policy
    )
    assert overridden.level == NdmoLevel.TOP_SECRET
