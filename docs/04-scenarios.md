# 04. Scenarios Checklist

Legend:
- **Tier:** M = MVP, S = Stretch
- **Status:** Pending, In Progress, Complete

| Check | ID | Scenario | Tier | Test file | Status |
|---|---|---|---|---|---|
| - [x] | S1 | Normal submission | M | tests/test_workflow.py | Complete |
| - [x] | S2 | Invalid or missing fields | M | tests/test_workflow.py | Complete |
| - [x] | S3 | Double submit | M | tests/test_workflow.py | Complete |
| - [ ] | S4 | Bad, large, or HEIC photo | M | | Pending |
| - [ ] | S5 | Bad preferred time | M | | Pending |
| - [ ] | S6 | Hostile, long, or Unicode text | M | | Pending |
| - [ ] | S7 | Duplicate suggestion | M | | Pending |
| - [x] | S8 | Recurrence link | S | tests/test_workflow.py | Complete |
| - [x] | S9 | Safety flag notice | M | tests/test_workflow.py | Complete |
| - [x] | S10 | Cancel rules | M | tests/test_workflow.py | Complete |
| - [ ] | S11 | Network-drop draft | S | | Pending |
| - [x] | S12 | IDOR returns 404 | M | tests/test_workflow.py | Complete |
| - [x] | S13 | Forged status change rejected | M | tests/test_workflow.py | Complete |
| - [x] | S14 | Technician not assigned denied | M | tests/test_workflow.py | Complete |
| - [ ] | S15 | Severity locked after assignment | M | | Pending |
| - [x] | S16 | Complete blocked without checklist | M | tests/test_workflow.py | Complete |
| - [ ] | S17 | Concurrent assignment conflict | M | | Pending |
| - [ ] | S18 | Priority override needs reason | M | | Pending |
| - [ ] | S19 | Deactivated technician reassignment | S | | Pending |
| - [ ] | S20 | No skill or overloaded stays in triage | M | | Pending |
| - [x] | S21 | Access failed pauses SLA | M | tests/test_workflow.py | Complete |
| - [ ] | S22 | Waiting for parts and stock guard | M | | Pending |
| - [x] | S23 | Reopen after "not fixed" | M | tests/test_workflow.py | Complete |
| - [x] | S24 | Unverified auto-close at 72h | M | tests/test_workflow.py | Complete |
| - [ ] | S25 | Common-area confirmation by any affected reporter | M | | Pending |
| - [x] | S26 | Reassignment preserves history | M | tests/test_workflow.py | Complete |
| - [ ] | S27 | Unmerge | S | | Pending |
| - [ ] | S28 | Recurring tasks do not stack | S | | Pending |
| - [ ] | S29 | SLA pause reporting | M | | Pending |
| - [x] | S30 | Lazy overdue evaluation | M | tests/test_workflow.py | Complete |
| - [ ] | S31 | Empty or degenerate reports | M | | Pending |
| - [ ] | S32 | 1000+ requests performance | M | | Pending |
| - [ ] | S33 | SMTP failure non-blocking | M | | Pending |
| - [x] | S34 | Friendly 500 with reference ID | M | tests/test_pages.py | Complete |
| - [x] | S35 | reset_demo | M | tests/test_reset_demo.py | Complete |
