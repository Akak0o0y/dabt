from dabt_core.detectors.mobile import SaudiMobileDetector


def test_detects_local_saudi_mobile() -> None:
    finding = SaudiMobileDetector().detect("Call 0501234567")[0]
    assert finding.type == "saudi_mobile"
    assert finding.confidence_tier == "format_detected"


def test_detects_international_saudi_mobile() -> None:
    finding = SaudiMobileDetector().detect("Call +966501234567")[0]
    assert finding.normalized_value == "+966501234567"


def test_ignores_non_mobile_local_prefix() -> None:
    assert SaudiMobileDetector().detect("0412345678") == []
