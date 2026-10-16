import yaml
from django.conf import settings

from tests.reference_priority import compute_priority_score_and_band


def load_priority_rules():
    yaml_path = settings.BASE_DIR / "docs" / "priority_rules.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_score_cap():
    pr = load_priority_rules()
    assert pr.get("score_cap") == 100


def test_bands_coverage_and_slas():
    pr = load_priority_rules()
    bands = pr.get("bands", [])
    assert len(bands) > 0

    for b in bands:
        assert "sla_hours" in b and b["sla_hours"] > 0, f"Band {b.get('id')} missing valid SLA"

    # Sort bands by min_score
    sorted_bands = sorted(bands, key=lambda x: x["min_score"])

    # Check first band starts at 0
    assert sorted_bands[0]["min_score"] == 0, f"Bands start at {sorted_bands[0]['min_score']}, expected 0"

    # Check last band ends at 100
    assert sorted_bands[-1]["max_score"] == 100, f"Bands end at {sorted_bands[-1]['max_score']}, expected 100"

    # Check continuity (no gaps, no overlaps)
    for i in range(len(sorted_bands) - 1):
        curr_max = sorted_bands[i]["max_score"]
        next_min = sorted_bands[i + 1]["min_score"]
        assert curr_max + 1 == next_min, (
            f"Gap or overlap between band {sorted_bands[i]['id']} (max {curr_max}) "
            f"and band {sorted_bands[i+1]['id']} (min {next_min})"
        )


def test_golden_examples_match_reference_scorer():
    pr = load_priority_rules()
    examples = pr.get("golden_examples", [])
    assert len(examples) == 8, f"Expected 8 golden examples, found {len(examples)}"

    for ex in examples:
        computed_score, computed_band = compute_priority_score_and_band(ex["inputs"])
        assert computed_score == ex["expected_score"], (
            f"Example {ex['id']} ({ex['description']}): computed score {computed_score} "
            f"!= expected {ex['expected_score']}"
        )
        assert computed_band == ex["expected_band"], (
            f"Example {ex['id']} ({ex['description']}): computed band {computed_band} "
            f"!= expected {ex['expected_band']}"
        )


def test_golden_examples_match_real_engine():
    from apps.tickets.priority import compute_priority_score_and_band as real

    for ex in load_priority_rules()["golden_examples"]:
        assert real(ex["inputs"]) == (ex["expected_score"], ex["expected_band"]), ex["description"]


def test_engine_bands_match_yaml():
    from apps.tickets.priority import BANDS

    yaml_bands = {b["id"]: (b["min_score"], b["max_score"], b["sla_hours"]) for b in load_priority_rules()["bands"]}
    assert {b["id"]: (b["min_score"], b["max_score"], b["sla_hours"]) for b in BANDS} == yaml_bands


def test_critical_location_keywords_use_whole_words(db):
    from apps.locations.models import Building, Location
    from apps.tickets.priority import is_critical_location

    b = Building.objects.create(name="Academic Block", code="AB")
    assert is_critical_location(Location.objects.create(building=b, name="Physics Lab")) is True
    assert is_critical_location(Location.objects.create(building=b, name="Collaboration Room")) is False
