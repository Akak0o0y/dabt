from __future__ import annotations

from pathlib import Path

import pytest

from dabt_core.loader import load_compliance_map
from dabt_core.schema import SchemaError


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_rejects_missing_confidence_level() -> None:
    with pytest.raises(SchemaError, match="INVALID-MISSING-CONFIDENCE.*confidence_level"):
        load_compliance_map(FIXTURES / "invalid_missing_confidence.yaml")


def test_load_rejects_missing_legal_review() -> None:
    with pytest.raises(SchemaError, match="INVALID-MISSING-LEGAL-REVIEW.*requires_legal_review"):
        load_compliance_map(FIXTURES / "invalid_missing_legal_review.yaml")


def test_load_accepts_valid_map() -> None:
    loaded = load_compliance_map(FIXTURES / "valid_minimal.yaml")
    assert loaded.rules[0].id == "VALID-MINIMAL"


def test_validation_happens_during_load() -> None:
    with pytest.raises(SchemaError):
        load_compliance_map(FIXTURES / "invalid_missing_confidence.yaml")

