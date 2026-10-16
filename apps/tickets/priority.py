"""Priority scoring and SLA calculation engine according to docs/priority_rules.yaml."""

from datetime import datetime, timedelta
from typing import Any

from apps.core import clock

SCORE_CAP = 100

SEVERITY_WEIGHTS = {
    "minor": 10,
    "moderate": 25,
    "major": 40,
    "critical": 50,
}

SAFETY_FLAG_BONUS = 30
AFFECTED_PER_PERSON_BONUS = 5
MAX_AFFECTED_BONUS = 15
CRITICAL_LOCATION_BONUS = 10
RECURRENCE_BONUS = 10

AGING_HALF_SLA_BONUS = 10
AGING_OVERDUE_BONUS = 20

CRITICAL_LOCATION_KEYWORDS = ["medical", "lab", "entrance", "mess", "clinic", "hospital"]

BANDS = [
    {
        "id": "P1",
        "name": "Critical",
        "min_score": 75,
        "max_score": 100,
        "sla_hours": 4,
    },
    {
        "id": "P2",
        "name": "High",
        "min_score": 55,
        "max_score": 74,
        "sla_hours": 24,
    },
    {
        "id": "P3",
        "name": "Medium",
        "min_score": 30,
        "max_score": 54,
        "sla_hours": 72,
    },
    {
        "id": "P4",
        "name": "Low",
        "min_score": 0,
        "max_score": 29,
        "sla_hours": 168,
    },
]


def get_band_for_score(score: int) -> dict[str, Any]:
    """Map a numerical score (0-100) to its corresponding priority band."""
    clamped_score = max(0, min(SCORE_CAP, score))
    for band in BANDS:
        if band["min_score"] <= clamped_score <= band["max_score"]:
            return band
    return BANDS[-1]


def compute_priority_score_and_band(inputs: dict[str, Any]) -> tuple[int, str]:
    """Pure calculation matching reference scorer and docs/priority_rules.yaml."""
    severity = str(inputs.get("severity", "minor")).lower()
    score = SEVERITY_WEIGHTS.get(severity, 10)

    if inputs.get("safety_flag", False):
        score += SAFETY_FLAG_BONUS

    additional_people = int(inputs.get("additional_affected_people", 0) or 0)
    extra_people_bonus = min(additional_people * AFFECTED_PER_PERSON_BONUS, MAX_AFFECTED_BONUS)
    score += extra_people_bonus

    if inputs.get("critical_location", False):
        score += CRITICAL_LOCATION_BONUS

    if inputs.get("recurrence", False):
        score += RECURRENCE_BONUS

    aging = str(inputs.get("aging", "none")).lower()
    if aging == "overdue":
        score += AGING_OVERDUE_BONUS
    elif aging == "half_sla":
        score += AGING_HALF_SLA_BONUS

    score = min(score, SCORE_CAP)
    band_info = get_band_for_score(score)
    return score, band_info["id"]


def calculate_ticket_priority(
    severity: str,
    safety_flag: bool = False,
    additional_affected_people: int = 0,
    is_critical_location: bool = False,
    has_recurrence: bool = False,
    created_at: datetime | None = None,
    sla_hours: int | None = None,
    total_paused_seconds: float = 0.0,
) -> tuple[int, str, int]:
    """Calculate the priority score, band ID, and SLA hours for a ticket model.

    Returns:
        (priority_score, priority_band_id, sla_hours)
    """
    aging_status = "none"
    if created_at and sla_hours:
        current_time = clock.now()
        effective_elapsed = (current_time - created_at).total_seconds() - total_paused_seconds
        sla_seconds = sla_hours * 3600.0
        if effective_elapsed >= sla_seconds:
            aging_status = "overdue"
        elif effective_elapsed >= (sla_seconds * 0.5):
            aging_status = "half_sla"

    inputs = {
        "severity": severity,
        "safety_flag": safety_flag,
        "additional_affected_people": additional_affected_people,
        "critical_location": is_critical_location,
        "recurrence": has_recurrence,
        "aging": aging_status,
    }

    score, band_id = compute_priority_score_and_band(inputs)
    band_meta = get_band_for_score(score)
    return score, band_id, band_meta["sla_hours"]


def calculate_sla_due_date(
    start_time: datetime, sla_hours: int, paused_seconds: float = 0.0
) -> datetime:
    """Compute the SLA deadline given start timestamp and hours."""
    return start_time + timedelta(hours=sla_hours, seconds=paused_seconds)
