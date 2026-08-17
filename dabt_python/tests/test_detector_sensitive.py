from dabt_core.detectors.sensitive import SensitiveDataDetector


def test_detects_health_data_in_english() -> None:
    finding = SensitiveDataDetector().detect("The patient medical diagnosis is in the report.")[0]
    assert finding.sensitive_category == "health"


def test_detects_sensitive_data_in_arabic() -> None:
    finding = SensitiveDataDetector().detect("يتضمن التقرير بيانات صحية وملفاً طبياً.")[0]
    assert finding.sensitive_category == "health"


def test_detects_each_article_1_11_category() -> None:
    text = "ethnicity religion political criminal biometric genetic health adoption"
    categories = {finding.sensitive_category for finding in SensitiveDataDetector().detect(text)}
    assert {"ethnic", "belief", "criminal", "biometric", "genetic", "health", "unknown_parentage"} <= categories


def test_benign_text_has_no_sensitive_findings() -> None:
    assert SensitiveDataDetector().detect("Public annual report for 2025.") == []
