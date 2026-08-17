from __future__ import annotations

import json
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from dabt_core.detectors.base import Finding
from dabt_core.engine import EngineRequest, PolicyEngine
from dabt_core.loader import load_compliance_map
from dabt_core.schema import ConfidenceLevel, Decision


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


class StaticDetector:
    def __init__(self, findings: list[Finding]) -> None:
        self.findings = findings

    def detect(self, text: str) -> list[Finding]:
        return self.findings


def sample_finding() -> Finding:
    return Finding("saudi_national_id", "1000000008", "1000000008", 3, 13, "checksum_verified", "verified", True)


def test_six_stages_execute_in_order() -> None:
    trace: list[str] = []
    result = PolicyEngine(load_compliance_map(MAP_PATH), (StaticDetector([sample_finding()]),)).evaluate(
        EngineRequest(document="ID 1000000008", cross_border=True),
        "2026-08-17T00:00:00Z",
        trace,
    )
    assert result.decision == Decision.ALLOW_WITH_REDACTION
    assert trace == ["detection", "classification", "policy_evaluation", "obligation_resolution", "redaction", "audit_logging"]


def test_rules_evaluated_in_priority_order_and_all_fired_recorded() -> None:
    result = PolicyEngine(load_compliance_map(MAP_PATH), (StaticDetector([sample_finding()]),)).evaluate(
        EngineRequest(document="ID 1000000008", cross_border=True), "2026-08-17T00:00:00Z"
    )
    fired_ids = [rule.id for rule in result.fired_rules]
    assert fired_ids == ["PDPL-ART29-2C-CROSSBORDER-MINIMISATION", "PDPL-ART15-5-ANONYMISED-DISCLOSURE", "PDPL-ART11-3-MINIMISATION"]
    assert result.decision_rule_id == "PDPL-ART29-2C-CROSSBORDER-MINIMISATION"


def test_needs_verification_rule_degrades_terminal_deny_to_review() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    first = compliance_map.rules[0]
    unverified_deny = replace(first, decision=Decision.DENY, confidence_level=ConfidenceLevel.NEEDS_VERIFICATION)
    result = PolicyEngine(replace(compliance_map, rules=(unverified_deny,)), ()).evaluate(
        EngineRequest(document="public", sector="security"), "2026-08-17T00:00:00Z"
    )
    assert result.decision == Decision.REVIEW


def test_determinism_same_input_is_byte_identical() -> None:
    engine = PolicyEngine(load_compliance_map(MAP_PATH), (StaticDetector([sample_finding()]),))
    request = EngineRequest(document="ID 1000000008", cross_border=True)
    first = json.dumps(engine.evaluate(request, "2026-08-17T00:00:00Z").to_dict(), sort_keys=True)
    second = json.dumps(engine.evaluate(request, "2026-08-17T00:00:00Z").to_dict(), sort_keys=True)
    assert first == second


def test_engine_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def prohibit_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "socket", prohibit_network)
    result = PolicyEngine(load_compliance_map(MAP_PATH), ()).evaluate(
        EngineRequest(document="public"), "2026-08-17T00:00:00Z"
    )
    assert result.decision == Decision.ALLOW
