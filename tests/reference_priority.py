"""Reference priority scorer for Phase 0 validation.

NOTE: replaced by the real engine in Phase 4; the real engine must pass the same examples.
"""


def compute_priority_score_and_band(inputs: dict) -> tuple[int, str]:
    severity_map = {
        "minor": 10,
        "moderate": 25,
        "major": 40,
        "critical": 50,
    }

    score = severity_map.get(inputs.get("severity", "minor"), 10)

    if inputs.get("safety_flag", False):
        score += 30

    extra_people = min(inputs.get("additional_affected_people", 0) * 5, 15)
    score += extra_people

    if inputs.get("critical_location", False):
        score += 10

    if inputs.get("recurrence", False):
        score += 10

    aging = inputs.get("aging", "none")
    if aging == "overdue":
        score += 20
    elif aging == "half_sla":
        score += 10

    score = min(score, 100)

    if score >= 75:
        band = "P1"
    elif score >= 55:
        band = "P2"
    elif score >= 30:
        band = "P3"
    else:
        band = "P4"

    return score, band
