from dabt_core.detectors.commercial_registration import CommercialRegistrationDetector


def test_detects_known_riyadh_commercial_registration_prefix() -> None:
    finding = CommercialRegistrationDetector().detect("CR 1010123456")[0]
    assert finding.type == "saudi_commercial_registration"
    assert finding.confidence_level == "inferred"


def test_detects_known_jeddah_and_dammam_prefixes() -> None:
    findings = CommercialRegistrationDetector().detect("4030123456 / 2050123456")
    assert [finding.value for finding in findings] == ["4030123456", "2050123456"]


def test_ignores_unknown_commercial_registration_prefix() -> None:
    assert CommercialRegistrationDetector().detect("9990123456") == []


def test_commercial_registration_counts_as_personal_data() -> None:
    finding = CommercialRegistrationDetector().detect("CR 1010123456 on file")[0]
    assert finding.is_personal_data is True
