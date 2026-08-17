from __future__ import annotations

from pathlib import Path

from dabt_core.loader import load_compliance_map


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def test_real_compliance_map_loads() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    assert len(compliance_map.rules) >= 10


def test_every_rule_has_verbatim_quote_and_bilingual_rationales() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    for rule in compliance_map.rules:
        assert rule.citation.quote.strip(), rule.id
        assert rule.rationale_en.strip(), rule.id
        assert rule.rationale_ar.strip(), rule.id


def test_every_entry_requires_legal_review() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    for rule in compliance_map.rules:
        assert rule.requires_legal_review is True, rule.id
        for mapped in rule.mapped_controls:
            assert mapped.requires_legal_review is True, f"{rule.id}:{mapped.control_id}"


def test_no_verified_ecc_leaf_control_is_claimed() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    for rule in compliance_map.rules:
        for mapped in rule.mapped_controls:
            assert not (
                mapped.framework == "NCA_ECC_2_2024"
                and mapped.granularity == "control"
                and mapped.confidence_level == "verified"
            ), f"{rule.id}:{mapped.control_id}"


def test_required_pdpl_legal_anchors_are_present() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    rules = {rule.id: rule for rule in compliance_map.rules}
    assert rules["PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST"].citation.article == "Article 6(4)"
    assert rules["PDPL-ART15-5-ANONYMISED-DISCLOSURE"].citation.article == "Article 15(5)"
    assert rules["PDPL-ART29-2C-CROSSBORDER-MINIMISATION"].citation.article == "Article 29(2)(c)"
