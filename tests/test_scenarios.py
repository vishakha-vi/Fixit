import re

from django.conf import settings


def test_all_35_scenarios_present_with_tier():
    doc_path = settings.BASE_DIR / "docs" / "04-scenarios.md"
    content = doc_path.read_text(encoding="utf-8")

    # Regular expression to extract rows containing ID and Tier
    # Pattern: | - [ ] | S<num> | ... | <Tier> | ... |
    found_scenarios = {}
    for line in content.splitlines():
        if "| S" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            # Find the part that starts with 'S' followed by digits
            sid = None
            for idx, part in enumerate(parts):
                if re.match(r"^S\d+$", part):
                    sid = part
                    # Next or next+1 is the description, followed by Tier (M or S)
                    for candidate in parts[idx + 1:]:
                        if candidate in ("M", "S"):
                            found_scenarios[sid] = candidate
                            break
                    break

    expected_ids = {f"S{i}" for i in range(1, 36)}
    missing_ids = expected_ids - set(found_scenarios.keys())

    assert not missing_ids, f"Scenarios missing from docs/04-scenarios.md: {sorted(missing_ids)}"
    assert len(found_scenarios) == 35, f"Expected 35 scenarios, found {len(found_scenarios)}"

    for sid, tier in found_scenarios.items():
        assert tier in ("M", "S"), f"Scenario {sid} has invalid tier '{tier}'"
