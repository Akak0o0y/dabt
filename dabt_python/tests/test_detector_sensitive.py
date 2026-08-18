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


def test_latin_terms_do_not_match_inside_longer_words() -> None:
    text = "The bracelet traced a graceful arc. Our loaner fleet is healthy."
    assert SensitiveDataDetector().detect(text) == []


def test_latin_terms_still_match_regular_plurals() -> None:
    categories = {f.sensitive_category for f in SensitiveDataDetector().detect("Races and ethnicities differ.")}
    assert categories == {"ethnic"}


def test_arabic_term_matches_through_attached_affixes() -> None:
    for form in ("\u0635\u062d\u064a", "\u0627\u0644\u0635\u062d\u064a\u0629", "\u0648\u0628\u0627\u0644\u0635\u062d\u064a\u0629"):
        findings = SensitiveDataDetector().detect(form)
        assert [f.sensitive_category for f in findings] == ["health"], form


def test_arabic_multi_word_term_matches_with_interior_definite_article() -> None:
    findings = SensitiveDataDetector().detect("\u0627\u0644\u0633\u062c\u0644 \u0627\u0644\u0627\u0626\u062a\u0645\u0627\u0646\u064a")
    assert [f.sensitive_category for f in findings] == ["credit"]


def test_arabic_unrelated_word_sharing_letters_is_not_matched() -> None:
    assert SensitiveDataDetector().detect("\u0645\u0635\u0628\u0627\u062d") == []


def test_redaction_span_covers_the_sentence_not_only_the_keyword() -> None:
    text = "Header note. The applicant provided a fingerprint template today. Unrelated tail."
    finding = SensitiveDataDetector().detect(text)[0]
    assert text[finding.start:finding.end] == "fingerprint"
    start, end = finding.redaction_span
    assert text[start:end] == "The applicant provided a fingerprint template today"
