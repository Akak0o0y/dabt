from pathlib import Path

from dabt_core.loader import load_compliance_map

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def test_map_exposes_in_kingdom_regions() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.residency, "residency table must not be empty"


def test_known_in_kingdom_region_is_recognised() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.region_in_kingdom("me-central-1") is True


def test_unrecognised_region_is_treated_as_outside_the_kingdom() -> None:
    # Conservative direction: an unknown region triggers the residency rule and
    # lands on REVIEW rather than passing unexamined.
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.region_in_kingdom("eu-west-1") is False
    assert compliance_map.region_in_kingdom("__never_heard_of_it__") is False


def test_every_region_entry_requires_legal_review() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    for region in compliance_map.residency:
        assert region.requires_legal_review is True, region.id
        assert region.confidence_level != "verified", region.id
