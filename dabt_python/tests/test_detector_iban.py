from dabt_core.detectors.iban import SaudiIbanDetector


def test_detects_valid_sa_iban() -> None:
    finding = SaudiIbanDetector().detect("Pay SA0380000000608010167519 now")[0]
    assert finding.type == "saudi_iban"
    assert finding.checksum_result is True
    assert finding.confidence_tier == "checksum_verified"


def test_mod97_invalid_still_yields_finding() -> None:
    finding = SaudiIbanDetector().detect("Pay SA0380000000608010167518 now")[0]
    assert finding.checksum_result is False
    assert finding.confidence_tier == "format_detected"


def test_normalises_print_format_with_spaces() -> None:
    finding = SaudiIbanDetector().detect("SA03 8000 0000 6080 1016 7519")[0]
    assert finding.normalized_value == "SA0380000000608010167519"
    assert finding.checksum_result is True


def test_ignores_non_sa_iban() -> None:
    assert SaudiIbanDetector().detect("GB82 WEST 1234 5698 7654 32") == []
