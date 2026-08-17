from dabt_core.obligations import RedactionObligation
from dabt_core.redactor import apply_redactions


def test_redacts_span_preserving_length_and_structure() -> None:
    source = "ID 1000000008 is attached."
    result = apply_redactions(source, [RedactionObligation(3, 13, "personal_data", "full")])
    assert result == "ID ██████████ is attached."
    assert len(result) == len(source)


def test_redaction_is_idempotent() -> None:
    source = "ID 1000000008"
    obligation = RedactionObligation(3, 13, "personal_data", "full")
    assert apply_redactions(apply_redactions(source, [obligation]), [obligation]) == apply_redactions(source, [obligation])


def test_overlapping_spans_merge() -> None:
    source = "ABCDEFGHIJ"
    result = apply_redactions(
        source,
        [RedactionObligation(2, 7, "personal_data", "full"), RedactionObligation(5, 9, "personal_data", "full")],
    )
    assert result == "AB███████J"


def test_partial_masking_preserves_last_four_where_configured() -> None:
    source = "1000000008"
    result = apply_redactions(source, [RedactionObligation(0, 10, "personal_data", "last_four")])
    assert result == "██████0008"
