from dabt_core.detectors.national_id import NationalIdDetector


def test_detects_national_id_leading_1() -> None:
    findings = NationalIdDetector().detect("National ID: 1000000008")
    assert len(findings) == 1
    assert findings[0].type == "saudi_national_id"
    assert findings[0].confidence_tier == "checksum_verified"


def test_detects_iqama_leading_2() -> None:
    findings = NationalIdDetector().detect("Iqama: 2000000006")
    assert len(findings) == 1
    assert findings[0].type == "iqama"
    assert findings[0].confidence_tier == "checksum_verified"


def test_luhn_invalid_still_yields_format_detected_finding() -> None:
    findings = NationalIdDetector().detect("Candidate number: 1000000000")
    assert len(findings) == 1
    assert findings[0].checksum_result is False
    assert findings[0].confidence_tier == "format_detected"


def test_ignores_9_and_11_digit_numbers() -> None:
    findings = NationalIdDetector().detect("100000008 and 10000000008")
    assert findings == []


def test_ignores_leading_digits_three_through_nine() -> None:
    findings = NationalIdDetector().detect("3000000000 9000000000")
    assert findings == []


def test_reports_correct_span_offsets() -> None:
    text = "ID=1000000008."
    finding = NationalIdDetector().detect(text)[0]
    assert text[finding.start : finding.end] == finding.value
