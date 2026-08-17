from dabt_core.audit import build_audit_record
from dabt_core.engine import EngineRequest, PolicyDecision
from dabt_core.loader import load_compliance_map
from dabt_core.schema import Decision


def test_record_contains_both_languages_and_disclaimers() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    rule = next(rule for rule in compliance_map.rules if rule.id == "PDPL-ART29-2C-CROSSBORDER-MINIMISATION")
    record = build_audit_record(
        EngineRequest(document="ID 1000000008", cross_border=True),
        "Confidential",
        PolicyDecision(Decision.ALLOW_WITH_REDACTION, rule, (rule,)),
        (),
        "2026-08-17T00:00:00Z",
    )
    assert record.summary_en
    assert record.summary_ar
    assert "legal" in record.legal_review_disclaimer_en.lower()
    assert "مراجعة" in record.legal_review_disclaimer_ar


def test_every_mapped_control_carries_its_own_confidence() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    rule = compliance_map.rules[0]
    record = build_audit_record(
        EngineRequest(document="public"), "Public", PolicyDecision(Decision.ALLOW, rule, (rule,)), (), "2026-08-17T00:00:00Z"
    )
    assert all(control["confidence_level"] for control in record.mapped_controls)


def test_no_record_claims_authoritative_status() -> None:
    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    rule = compliance_map.rules[0]
    record = build_audit_record(
        EngineRequest(document="public"), "Public", PolicyDecision(Decision.ALLOW, rule, (rule,)), (), "2026-08-17T00:00:00Z"
    )
    blob = str(record.to_dict()).casefold()
    assert "authoritative" not in blob


def test_record_is_json_serialisable() -> None:
    import json

    compliance_map = load_compliance_map("dabt_core/data/compliance_map.yaml")
    rule = compliance_map.rules[0]
    record = build_audit_record(
        EngineRequest(document="public"), "Public", PolicyDecision(Decision.ALLOW, rule, (rule,)), (), "2026-08-17T00:00:00Z"
    )
    assert json.loads(json.dumps(record.to_dict()))["decision"] == "ALLOW"
