"""Ticket lifecycle engine driven by docs/state_machine.yaml.

The YAML file is the single source of truth for states, allowed transitions and
which workflow role may perform them. Guards named in the YAML are enforced by
the functions in GUARDS below.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache

import yaml
from django.conf import settings
from django.db import transaction

from apps.accounts import features as F
from apps.core import clock
from apps.tickets.models import Ticket, TicketEvent

REQUESTER = "requester"
TECHNICIAN = "technician"
ADMIN = "admin"
SYSTEM = "system"

COLOR_CLASSES = {
    "blue": "primary",
    "grey": "secondary",
    "amber": "warning",
    "green": "success",
    "red": "danger",
}


class TransitionError(Exception):
    """Raised when a requested status change is not allowed."""


@lru_cache(maxsize=1)
def load_spec() -> dict:
    with open(settings.BASE_DIR / "docs" / "state_machine.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def state_meta(status: str) -> dict:
    return load_spec()["states"].get(status, {})


def status_color_class(status: str) -> str:
    return COLOR_CLASSES.get(state_meta(status).get("color", "grey"), "secondary")


def transitions_from(status: str) -> list[dict]:
    return [t for t in load_spec()["transitions"] if t["from"] == status]


def find_transition(from_status: str, to_status: str) -> dict | None:
    for t in load_spec()["transitions"]:
        if t["from"] == from_status and t["to"] == to_status:
            return t
    return None


def workflow_roles(user) -> set[str]:
    """Map a FixIt user (role + admin-granted features) onto state machine roles."""
    if user is None:
        return {SYSTEM}
    roles = set()
    if user.has_feature(F.MANAGE_COMPLAINTS):
        roles.add(ADMIN)
    if user.has_feature(F.WORK_ON_COMPLAINTS):
        roles.add(TECHNICIAN)
    if user.has_feature(F.TRACK_COMPLAINT) or user.has_feature(F.SUBMIT_COMPLAINT):
        roles.add(REQUESTER)
    return roles


# ---------------------------------------------------------------------------
# Guards: each returns an error message, or None when the guard passes.
# ---------------------------------------------------------------------------


def _is_owner(ticket, user):
    return user is not None and ticket.created_by_id == user.id


def _guard_technician_active(ticket, user, role, data, now):
    assignee = data.get("assignee") or ticket.assigned_to
    if assignee is None:
        return "Choose a worker to assign."
    if not assignee.is_active or not assignee.has_feature(F.WORK_ON_COMPLAINTS):
        return "The selected worker is not active."
    return None


def _guard_requester_is_owner(ticket, user, role, data, now):
    if role == REQUESTER and not _is_owner(ticket, user):
        return "Only the person who raised this complaint can do that."
    return None


def _guard_noop(ticket, user, role, data, now):
    return None


def _guard_reason_required(ticket, user, role, data, now):
    if not (data.get("reason") or "").strip():
        return "Please give a reason."
    return None


def _guard_target_required(ticket, user, role, data, now):
    target = data.get("target")
    if target is None:
        return "Choose the complaint to merge into."
    if target.pk == ticket.pk:
        return "A complaint cannot be merged into itself."
    if target.status in (Ticket.Status.MERGED, Ticket.Status.CANCELLED, Ticket.Status.REJECTED):
        return "Cannot merge into a closed complaint."
    return None


def _guard_technician_is_assigned(ticket, user, role, data, now):
    if role == TECHNICIAN and (user is None or ticket.assigned_to_id != user.id):
        return "Only the assigned worker can do that."
    return None


def _guard_checklist_complete(ticket, user, role, data, now):
    if not data.get("checklist"):
        return "Confirm the completion checklist before reporting the job fixed."
    return None


def _guard_verify(ticket, user, role, data, now):
    if role == REQUESTER:
        return None if _is_owner(ticket, user) else "Only the requester can confirm the fix."
    if role == TECHNICIAN:
        if ticket.assigned_to_id != user.id:
            return "Only the assigned worker can verify with a code."
        if (data.get("code") or "").strip() != ticket.completion_code:
            return "The completion code is not correct. Ask the requester for their 6-digit code."
        return None
    return "Not allowed."


def _guard_owner_or_affected(ticket, user, role, data, now):
    if role == REQUESTER and not _is_owner(ticket, user):
        return "Only the requester can reopen this complaint."
    return None


def _guard_within_reopen_window(ticket, user, role, data, now):
    window_days = state_meta(ticket.status).get("reopen_window_days")
    closed = ticket.closed_at or ticket.verified_at
    if window_days and closed and now - closed > timedelta(days=window_days):
        return f"The {window_days}-day reopen window has passed. Please raise a new complaint."
    return None


def _guard_after_72h(ticket, user, role, data, now):
    if not ticket.reported_fixed_at or now - ticket.reported_fixed_at < timedelta(hours=72):
        return "Auto-close happens only 72 hours after the fix was reported."
    return None


GUARDS = {
    "technician active": _guard_technician_active,
    "requester is owner": _guard_requester_is_owner,
    "not allowed once IN_PROGRESS": _guard_noop,
    "reason required": _guard_reason_required,
    "target request required": _guard_target_required,
    "technician is assigned": _guard_technician_is_assigned,
    # Incremented as a side effect when entering WAITING_ACCESS
    "attempt counter": _guard_noop,
    "checklist complete": _guard_checklist_complete,
    # Photo uploads are not part of the MVP; nothing to check yet
    "after-photo if category requires it": _guard_noop,
    "requester is owner or affected reporter; OR technician is assigned with valid "
    "completion code (method = on_site_code)": _guard_verify,
    "requester is owner or affected reporter": _guard_owner_or_affected,
    "within reopen window": _guard_within_reopen_window,
    "after 72h without a response": _guard_after_72h,
}


def _check_guards(transition, ticket, user, role, data, now):
    for guard in transition.get("guards") or []:
        check = GUARDS.get(guard)
        if check is None:
            return f"Unknown guard in state machine: {guard}"
        error = check(ticket, user, role, data, now)
        if error:
            return error
    return None


# ---------------------------------------------------------------------------
# UI metadata for each target state
# ---------------------------------------------------------------------------

ACTIONS = {
    "TRIAGED": {"label": "Mark as reviewed", "style": "outline-primary", "fields": []},
    "ASSIGNED": {"label": "Assign worker", "style": "primary", "fields": ["assignee"]},
    "IN_PROGRESS": {"label": "Start work", "style": "primary", "fields": []},
    "WAITING_PARTS": {"label": "Waiting for parts", "style": "outline-secondary", "fields": ["reason"]},
    "WAITING_ACCESS": {
        "label": "Could not access the room",
        "style": "outline-secondary",
        "fields": ["reason"],
    },
    "REPORTED_FIXED": {
        "label": "Report fixed",
        "style": "warning",
        "fields": ["checklist", "work_notes", "material_cost", "code_optional"],
    },
    "VERIFIED_FIXED": {"label": "Yes, it is fixed", "style": "success", "fields": []},
    "REOPENED": {"label": "Not fixed - reopen", "style": "outline-danger", "fields": ["reason"]},
    "CANCELLED": {"label": "Cancel complaint", "style": "outline-danger", "fields": ["reason_optional"]},
    "REJECTED": {"label": "Reject", "style": "outline-danger", "fields": ["reason"]},
    "MERGED": {"label": "Merge as duplicate", "style": "outline-secondary", "fields": ["target"]},
}

# Guards that depend on form input are checked on submit, not when listing actions
INPUT_GUARDS = {
    "technician active",
    "reason required",
    "target request required",
    "checklist complete",
}


def available_actions(ticket, user) -> list[dict]:
    """Status changes the user could make right now, with UI hints."""
    now = clock.now()
    user_roles = workflow_roles(user)
    actions = []
    for transition in transitions_from(ticket.status):
        for role in transition["roles"]:
            if role not in user_roles:
                continue
            static = {**transition, "guards": [
                g for g in (transition.get("guards") or []) if g not in INPUT_GUARDS
            ]}
            data = {"code": ticket.completion_code} if role == TECHNICIAN else {}
            if _check_guards(static, ticket, user, role, data, now):
                continue
            meta = dict(ACTIONS.get(transition["to"], {"label": transition["to"], "fields": []}))
            if transition["to"] == "IN_PROGRESS" and ticket.status != Ticket.Status.ASSIGNED:
                meta["label"] = "Resume work"
            if transition["to"] == "VERIFIED_FIXED" and role == TECHNICIAN:
                meta = {
                    "label": "Verify with completion code",
                    "style": "outline-success",
                    "fields": ["code"],
                }
            if transition["to"] == "ASSIGNED" and ticket.status == Ticket.Status.REOPENED:
                meta["label"] = "Assign again"
            actions.append({"to": transition["to"], "role": role, **meta})
            break
    return actions


def can_reassign(ticket, user) -> bool:
    event = load_spec()["events"]["reassign"]
    return (
        ticket.status in event["allowed_in_states"]
        and bool(workflow_roles(user) & set(event["roles"]))
    )


# ---------------------------------------------------------------------------
# Applying transitions
# ---------------------------------------------------------------------------


def _parse_money(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise TransitionError("Material cost must be a number.") from exc
    if amount < 0 or amount > Decimal("1000000"):
        raise TransitionError("Material cost must be between 0 and 10,00,000.")
    return amount


def _apply_sla(ticket, old_status, new_status, now):
    old_behavior = state_meta(old_status).get("sla_behavior")
    new_behavior = state_meta(new_status).get("sla_behavior")

    if old_behavior == "paused" and ticket.paused_since:
        ticket.paused_seconds += (now - ticket.paused_since).total_seconds()
        ticket.paused_since = None

    if new_behavior == "paused":
        ticket.paused_since = now
    elif new_behavior == "stopped":
        ticket.sla_stopped_at = ticket.sla_stopped_at or now
    elif new_behavior == "running" and ticket.sla_stopped_at:
        # Reopened work gets a fresh SLA window
        ticket.sla_due_at = now + timedelta(hours=ticket.sla_hours)
        ticket.paused_seconds = 0.0
        ticket.sla_stopped_at = None


def perform_transition(ticket, user, to_status, data=None, expected_status=None):
    """Validate and apply a status change. Returns the updated ticket."""
    from apps.tickets import services

    data = dict(data or {})
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if expected_status and ticket.status != expected_status:
            raise TransitionError(
                "This complaint was just updated by someone else. Please review it and try again."
            )

        transition = find_transition(ticket.status, to_status)
        if transition is None:
            raise TransitionError(
                f"Cannot move from {ticket.get_status_display()} to {to_status.replace('_', ' ').title()}."
            )

        now = clock.now()
        user_roles = workflow_roles(user)
        candidate_roles = [r for r in transition["roles"] if r in user_roles]
        if not candidate_roles:
            raise TransitionError("You are not allowed to make this change.")

        errors = []
        acting_role = None
        for role in candidate_roles:
            error = _check_guards(transition, ticket, user, role, data, now)
            if error is None:
                acting_role = role
                break
            errors.append(error)
        if acting_role is None:
            raise TransitionError(errors[0])

        old_status = ticket.status
        reason = (data.get("reason") or "").strip()
        message = reason

        if to_status == Ticket.Status.ASSIGNED:
            assignee = data.get("assignee") or ticket.assigned_to
            if assignee is None:
                raise TransitionError("Choose a worker to assign.")
            ticket.assigned_to = assignee
            ticket.assigned_at = now
            message = f"Assigned to {assignee.display_name}"
        elif to_status == Ticket.Status.IN_PROGRESS:
            worker = ticket.assigned_to
            if worker:
                worker.current_location = ticket.location
                worker.location_updated_at = now
                worker.save(update_fields=["current_location", "location_updated_at"])
        elif to_status == Ticket.Status.WAITING_ACCESS:
            ticket.access_attempts += 1
            message = f"Access attempt {ticket.access_attempts} failed: {reason}"
        elif to_status == Ticket.Status.REPORTED_FIXED:
            ticket.reported_fixed_at = now
            ticket.work_notes = (data.get("work_notes") or "").strip()
            ticket.material_cost = _parse_money(data.get("material_cost"))
            message = ticket.work_notes or "Work completed"
        elif to_status == Ticket.Status.VERIFIED_FIXED:
            ticket.verified_at = now
            ticket.closed_at = now
            ticket.verified_method = (
                Ticket.VerifiedMethod.ON_SITE_CODE
                if acting_role == TECHNICIAN
                else Ticket.VerifiedMethod.REQUESTER_CONFIRM
            )
            message = ticket.get_verified_method_display()
        elif to_status == Ticket.Status.REOPENED:
            ticket.reopen_count += 1
            ticket.reported_fixed_at = None
            ticket.verified_at = None
            ticket.verified_method = ""
            ticket.closed_at = None
        elif to_status in (
            Ticket.Status.CLOSED_UNVERIFIED,
            Ticket.Status.CANCELLED,
            Ticket.Status.REJECTED,
            Ticket.Status.MERGED,
        ):
            ticket.closed_at = now
            if to_status == Ticket.Status.MERGED:
                ticket.merged_into = data["target"]
                message = f"Merged into {data['target'].code}"
            if to_status == Ticket.Status.CLOSED_UNVERIFIED:
                message = "Closed automatically: no confirmation within 72 hours"

        _apply_sla(ticket, old_status, to_status, now)
        ticket.status = to_status
        ticket.save()

        TicketEvent.objects.create(
            ticket=ticket,
            actor=user,
            kind=TicketEvent.Kind.ASSIGNED if to_status == Ticket.Status.ASSIGNED
            else TicketEvent.Kind.STATUS,
            from_status=old_status,
            to_status=to_status,
            message=message,
            created_at=now,
        )
        services.after_transition(ticket, user, old_status, to_status, now)
    return ticket


def reassign(ticket, user, assignee, reason=""):
    from apps.tickets import services

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if not can_reassign(ticket, user):
            raise TransitionError("You are not allowed to reassign this complaint.")
        if assignee is None or not assignee.is_active or not assignee.has_feature(
            F.WORK_ON_COMPLAINTS
        ):
            raise TransitionError("Choose an active worker.")
        if assignee.pk == ticket.assigned_to_id:
            raise TransitionError("The complaint is already assigned to that worker.")
        now = clock.now()
        previous = ticket.assigned_to
        ticket.assigned_to = assignee
        ticket.assigned_at = now
        ticket.save()
        note = f"Reassigned from {previous.display_name if previous else 'nobody'} to {assignee.display_name}"
        if reason:
            note += f": {reason.strip()}"
        TicketEvent.objects.create(
            ticket=ticket, actor=user, kind=TicketEvent.Kind.REASSIGNED, message=note, created_at=now
        )
        services.notify(
            assignee,
            f"New job: {ticket.code} {ticket.title} at {ticket.location}",
            ticket=ticket,
            kind="new_job",
            created_by=user,
        )
    return ticket
