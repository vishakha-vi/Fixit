# 04. Scenarios Checklist

Legend:
- **Tier:** M = MVP, S = Stretch
- **Status:** Pending, In Progress, Complete

| Check | ID | Scenario | Tier | Test file | Status |
|---|---|---|---|---|---|
| - [ ] | S1 | Normal submission | M | | Pending |
| - [ ] | S2 | Invalid or missing fields | M | | Pending |
| - [ ] | S3 | Double submit | M | | Pending |
| - [ ] | S4 | Bad, large, or HEIC photo | M | | Pending |
| - [ ] | S5 | Bad preferred time | M | | Pending |
| - [ ] | S6 | Hostile, long, or Unicode text | M | | Pending |
| - [ ] | S7 | Duplicate suggestion | M | | Pending |
| - [ ] | S8 | Recurrence link | S | | Pending |
| - [ ] | S9 | Safety flag notice | M | | Pending |
| - [ ] | S10 | Cancel rules | M | | Pending |
| - [ ] | S11 | Network-drop draft | S | | Pending |
| - [ ] | S12 | IDOR returns 404 | M | | Pending |
| - [ ] | S13 | Forged status change rejected | M | | Pending |
| - [ ] | S14 | Technician not assigned denied | M | | Pending |
| - [ ] | S15 | Severity locked after assignment | M | | Pending |
| - [ ] | S16 | Complete blocked without checklist | M | | Pending |
| - [ ] | S17 | Concurrent assignment conflict | M | | Pending |
| - [ ] | S18 | Priority override needs reason | M | | Pending |
| - [ ] | S19 | Deactivated technician reassignment | S | | Pending |
| - [ ] | S20 | No skill or overloaded stays in triage | M | | Pending |
| - [ ] | S21 | Access failed pauses SLA | M | | Pending |
| - [ ] | S22 | Waiting for parts and stock guard | M | | Pending |
| - [ ] | S23 | Reopen after "not fixed" | M | | Pending |
| - [ ] | S24 | Unverified auto-close at 72h | M | | Pending |
| - [ ] | S25 | Common-area confirmation by any affected reporter | M | | Pending |
| - [ ] | S26 | Reassignment preserves history | M | | Pending |
| - [ ] | S27 | Unmerge | S | | Pending |
| - [ ] | S28 | Recurring tasks do not stack | S | | Pending |
| - [ ] | S29 | SLA pause reporting | M | | Pending |
| - [ ] | S30 | Lazy overdue evaluation | M | | Pending |
| - [ ] | S31 | Empty or degenerate reports | M | | Pending |
| - [ ] | S32 | 1000+ requests performance | M | | Pending |
| - [ ] | S33 | SMTP failure non-blocking | M | | Pending |
| - [x] | S34 | Friendly 500 with reference ID | M | tests/test_pages.py | Complete |
| - [x] | S35 | reset_demo | M | tests/test_reset_demo.py | Complete |
