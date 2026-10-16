# 01. State Machine Specification

The FixIt ticket lifecycle state machine is formally defined in [`docs/state_machine.yaml`](state_machine.yaml).

## State Definitions

| State | SLA Behavior | Label | Color | Terminal | Reopenable |
|---|---|---|---|---|---|
| `SUBMITTED` | Running | Submitted | Blue | No | No |
| `TRIAGED` | Running | Reviewed by admin | Blue | No | No |
| `ASSIGNED` | Running | Assigned | Blue | No | No |
| `IN_PROGRESS` | Running | In progress | Blue | No | No |
| `WAITING_PARTS` | Paused | Waiting for parts | Grey | No | No |
| `WAITING_ACCESS` | Paused | Waiting for access | Grey | No | No |
| `REPORTED_FIXED` | Stopped | Technician reports fixed - awaiting your confirmation | **Amber** | No | No |
| `VERIFIED_FIXED` | Stopped | Confirmed fixed | **Green** | **Yes** | Yes (7 days) |
| `REOPENED` | Running | Reopened | Red | No | No |
| `CLOSED_UNVERIFIED` | Stopped | Closed - not confirmed | Grey | **Yes** | Yes (7 days) |
| `CANCELLED` | Stopped | Cancelled | Grey | **Yes** | No |
| `REJECTED` | Stopped | Rejected | Grey | **Yes** | No |
| `MERGED` | Stopped | Merged | Grey | **Yes** | No |

> [!IMPORTANT]
> **Aesthetic and Semantic Rule:**
> `VERIFIED_FIXED` is the **only** state configured with the color **Green**.
> `REPORTED_FIXED` is configured with **Amber**.
> This structural invariant enforces the product thesis: a technician reporting completion is never presented as a resolved fix until confirmed by the resident or verified via an on-site completion code.

---

## Allowed Transitions and Roles

| From State | To State | Allowed Roles | Guards & Preconditions |
|---|---|---|---|
| `SUBMITTED` | `TRIAGED` | admin | None |
| `SUBMITTED` | `ASSIGNED` | admin | Technician active |
| `TRIAGED` | `ASSIGNED` | admin | Technician active |
| `SUBMITTED` | `CANCELLED` | requester, admin | Requester is owner; not allowed once in progress |
| `TRIAGED` | `CANCELLED` | requester, admin | Requester is owner; not allowed once in progress |
| `ASSIGNED` | `CANCELLED` | requester, admin | Requester is owner; not allowed once in progress |
| `SUBMITTED` | `REJECTED` | admin | Rejection reason required |
| `TRIAGED` | `REJECTED` | admin | Rejection reason required |
| `SUBMITTED` | `MERGED` | admin | Target request required |
| `TRIAGED` | `MERGED` | admin | Target request required |
| `ASSIGNED` | `IN_PROGRESS` | technician, admin | Technician is assigned |
| `REOPENED` | `IN_PROGRESS` | technician, admin | Technician is assigned |
| `IN_PROGRESS` | `WAITING_PARTS` | technician, admin | Assigned technician; parts reason required |
| `IN_PROGRESS` | `WAITING_ACCESS` | technician, admin | Assigned technician; access reason required, increment attempt counter |
| `WAITING_PARTS` | `IN_PROGRESS` | technician, admin | Assigned technician |
| `WAITING_ACCESS` | `IN_PROGRESS` | technician, admin | Assigned technician |
| `IN_PROGRESS` | `REPORTED_FIXED` | technician, admin | Assigned technician; checklist completed, after-photo if category requires |
| `REPORTED_FIXED` | `VERIFIED_FIXED` | requester, technician | Requester is owner or affected; OR technician with valid completion code |
| `REPORTED_FIXED` | `REOPENED` | requester, admin | Reason required; within 7-day reopen window |
| `VERIFIED_FIXED` | `REOPENED` | requester, admin | Reason required; within 7-day reopen window |
| `CLOSED_UNVERIFIED` | `REOPENED` | requester, admin | Reason required; within 7-day reopen window |
| `REPORTED_FIXED` | `CLOSED_UNVERIFIED` | system | Automatic transition after 72 hours without requester response |
| `REOPENED` | `ASSIGNED` | admin | None |

---

## Special Events (Non-State Changes)

- **Reassignment:**
  - Performed by `admin` only.
  - Permitted while ticket is in `ASSIGNED`, `IN_PROGRESS`, `WAITING_PARTS`, `WAITING_ACCESS`, or `REOPENED`.
  - Reassignment updates the assigned technician and appends to the ticket history without resetting ticket state.
