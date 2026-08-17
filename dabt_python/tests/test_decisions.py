from __future__ import annotations

from pathlib import Path

from dabt_core.engine import EngineRequest, PolicyEngine
from dabt_core.loader import load_compliance_map
from dabt_core.schema import Decision


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def engine() -> PolicyEngine:
    return PolicyEngine(load_compliance_map(MAP_PATH))


def test_public_document_allows() -> None:
    result = engine().evaluate(EngineRequest(document="Public annual report 2025."), "2026-08-17T00:00:00Z")
    assert result.decision == Decision.ALLOW
    assert result.decision_rule_id == "NDMO-PUBLIC-ALLOW"


def test_pii_crossborder_allows_only_with_redaction() -> None:
    result = engine().evaluate(EngineRequest(document="National ID 1000000008", cross_border=True), "2026-08-17T00:00:00Z")
    assert result.decision == Decision.ALLOW_WITH_REDACTION
    assert result.decision_rule_id == "PDPL-ART29-2C-CROSSBORDER-MINIMISATION"
    assert "1000000008" not in result.redacted_document


def test_sensitive_data_under_legitimate_interest_denies() -> None:
    result = engine().evaluate(
        EngineRequest(document="The medical diagnosis is confidential.", lawful_basis="legitimate_interest"),
        "2026-08-17T00:00:00Z",
    )
    assert result.decision == Decision.DENY
    assert result.decision_rule_id == "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST"
    assert "medical diagnosis" not in result.redacted_document
    assert "DENIED" in result.redacted_document


def test_top_secret_sector_default_denies() -> None:
    result = engine().evaluate(EngineRequest(document="Public overview", sector="security"), "2026-08-17T00:00:00Z")
    assert result.decision == Decision.DENY
    assert result.decision_rule_id == "NDMO-TOP-SECRET-DENY"


def test_health_data_reviews() -> None:
    result = engine().evaluate(EngineRequest(document="The patient medical diagnosis is attached.", lawful_basis="consent"), "2026-08-17T00:00:00Z")
    assert result.decision == Decision.REVIEW
    assert result.decision_rule_id == "PDPL-ART23-HEALTH-DATA-RESTRICTION"


def test_decision_has_legal_review_disclaimer_in_both_languages() -> None:
    result = engine().evaluate(EngineRequest(document="Public annual report."), "2026-08-17T00:00:00Z")
    assert "legal" in result.audit.legal_review_disclaimer_en.lower()
    assert "مراجعة" in result.audit.legal_review_disclaimer_ar
