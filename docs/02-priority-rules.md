# 02. Priority Rules and SLA Specification

The FixIt ticket scoring and SLA bands are formally defined in [`docs/priority_rules.yaml`](file:///c:/Users/MAHENDRA/Desktop/hackvision%20website/docs/priority_rules.yaml).

## Scoring Formula

A ticket's priority score is calculated as a composite sum capped at **100**:

$$\text{Priority Score} = \min(100, \text{Severity} + \text{Safety} + \text{Affected People} + \text{Location} + \text{Recurrence} + \text{Aging})$$

### 1. Severity Weights
- **Minor:** 10
- **Moderate:** 25
- **Major:** 40
- **Critical:** 50

### 2. Modifiers
- **Safety Flag:** +30 (also requires admin acknowledgment within 30 minutes).
- **Additional Affected People:** +5 per person, up to a maximum bonus of +15 (3+ people).
- **Critical Location:** +10 (designated zones: medical room, laboratory, campus entrance, mess hall).
- **Recurrence:** +10 if a matching issue occurred on the same asset within the last 30 days.
- **Aging (Non-cumulative):**
  - +10 once at least 50% of the SLA duration has elapsed.
  - +20 once the SLA is overdue.

---

## Priority Bands and SLAs

| Band | Score Range | SLA Response/Resolution | Operational Description |
|---|---|---|---|
| **P1** | 75 – 100 | **4 hours** | Critical emergency requiring immediate dispatch and continuous escalation. |
| **P2** | 55 – 74 | **24 hours** | High urgency (safety hazard, multiple residents affected, core facility). |
| **P3** | 30 – 54 | **72 hours** | Routine breakdown or moderate inconvenience. |
| **P4** | 0 – 29 | **7 days (168 hours)** | Low urgency, aesthetic repair, or deferred maintenance. |

*Note: These bands provide full 0–100 coverage without gaps or overlaps. They represent configurable defaults to be reviewed and validated with the campus maintenance office.*

---

## Golden Scenarios

| # | Description | Inputs | Score | Band |
|---|---|---|---|---|
| 1 | Minor, no flags | Minor (10) | 10 | P4 |
| 2 | Moderate, 2 extra affected | Moderate (25) + 2×5 (10) | 35 | P3 |
| 3 | Major + safety | Major (40) + Safety (30) | 70 | P2 |
| 4 | Critical + safety | Critical (50) + Safety (30) | 80 | P1 |
| 5 | Major + critical location + recurrence | Major (40) + Location (10) + Recurrence (10) | 60 | P2 |
| 6 | Moderate + critical location + overdue | Moderate (25) + Location (10) + Overdue (20) | 55 | P2 |
| 7 | Minor + aging at 50% SLA | Minor (10) + Half-SLA (10) | 20 | P4 |
| 8 | Critical + safety + critical location + recurrence + 3 extra affected + overdue | Critical (50) + Safety (30) + Location (10) + Recurrence (10) + Affected (15) + Overdue (20) = 135 -> Capped | 100 | P1 |
