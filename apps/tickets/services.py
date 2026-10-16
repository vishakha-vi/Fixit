"""Complaint services: creation, visibility, notifications and the due-task monitor."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts import features as F
from apps.accounts.models import User
from apps.core import clock
from apps.tickets import priority
from apps.tickets.models import Reminder, Ticket, TicketEvent

logger = logging.getLogger(__name__)

RECURRENCE_DAYS = 30
DOUBLE_SUBMIT_SECONDS = 120
UNASSIGNED_REMINDER_HOURS = 2
CONFIRM_REMINDER_HOURS = 24
MANUAL_REMINDER_COOLDOWN_MINUTES = 10
DUE_TASKS_INTERVAL_SECONDS = 60

CLOSED_FOR_RECURRENCE = [Ticket.Status.CANCELLED, Ticket.Status.REJECTED, Ticket.Status.MERGED]
RUNNING_STATUSES = [
    Ticket.Status.SUBMITTED,
    Ticket.Status.TRIAGED,
    Ticket.Status.ASSIGNED,
    Ticket.Status.IN_PROGRESS,
    Ticket.Status.REOPENED,
]


# ---------------------------------------------------------------------------
# Who sees what
# ---------------------------------------------------------------------------


def visible_tickets(user):
    qs = Ticket.objects.select_related("location__building", "created_by", "assigned_to")
    if not user.is_authenticated:
        return qs.none()
    if user.has_feature(F.VIEW_ALL_COMPLAINTS) or user.has_feature(F.MANAGE_COMPLAINTS):
        return qs
    condition = Q(pk__in=[])
    if user.has_feature(F.TRACK_COMPLAINT) or user.has_feature(F.SUBMIT_COMPLAINT):
        condition |= Q(created_by=user)
    if user.has_feature(F.WORK_ON_COMPLAINTS):
        condition |= Q(assigned_to=user)
    return qs.filter(condition)


def can_participate(ticket, user) -> bool:
    """Comment / send reminders: requester, assigned worker or complaint managers."""
    return (
        user.has_feature(F.MANAGE_COMPLAINTS)
        or (ticket.created_by_id == user.id)
        or (ticket.assigned_to_id == user.id)
    )


def managers() -> list[User]:
    return [u for u in User.objects.filter(is_active=True) if u.has_feature(F.MANAGE_COMPLAINTS)]


def active_workers():
    users = User.objects.filter(is_active=True).select_related("area", "current_location__building")
    return [u for u in users if u.has_feature(F.WORK_ON_COMPLAINTS) and not u.is_admin_role()]


def open_job_counts() -> dict[int, int]:
    counts = {}
    for worker_id in Ticket.objects.filter(
        status__in=Ticket.ACTIVE_WORK_STATUSES, assigned_to__isnull=False
    ).values_list("assigned_to_id", flat=True):
        counts[worker_id] = counts.get(worker_id, 0) + 1
    return counts


def similar_open_tickets(ticket, limit=5):
    return (
        Ticket.objects.filter(
            location=ticket.location, category=ticket.category, status__in=Ticket.OPEN_STATUSES
        )
        .exclude(pk=ticket.pk)
        .order_by("-created_at")[:limit]
    )


# ---------------------------------------------------------------------------
# Creating complaints
# ---------------------------------------------------------------------------


def create_ticket(
    *,
    created_by,
    title,
    description,
    category,
    severity,
    location,
    location_detail="",
    safety_flag=False,
    affected_people=0,
):
    """Create a complaint with its priority and SLA. Returns (ticket, created)."""
    now = clock.now()
    duplicate = Ticket.objects.filter(
        created_by=created_by,
        title__iexact=title.strip(),
        location=location,
        created_at__gte=now - timedelta(seconds=DOUBLE_SUBMIT_SECONDS),
    ).first()
    if duplicate:
        return duplicate, False

    recurrence = (
        Ticket.objects.filter(
            location=location,
            category=category,
            created_at__gte=now - timedelta(days=RECURRENCE_DAYS),
        )
        .exclude(status__in=CLOSED_FOR_RECURRENCE)
        .exists()
    )
    score, band, sla_hours = priority.calculate_ticket_priority(
        severity=severity,
        safety_flag=safety_flag,
        additional_affected_people=affected_people,
        is_critical_location=priority.is_critical_location(location),
        has_recurrence=recurrence,
    )
    with transaction.atomic():
        ticket = Ticket.objects.create(
            title=title.strip(),
            description=description.strip(),
            category=category,
            severity=severity,
            safety_flag=safety_flag,
            affected_people=affected_people,
            location=location,
            location_detail=location_detail.strip(),
            created_by=created_by,
            priority_score=score,
            priority_band=band,
            is_recurrence=recurrence,
            sla_hours=sla_hours,
            sla_due_at=now + timedelta(hours=sla_hours),
            created_at=now,
        )
        TicketEvent.objects.create(
            ticket=ticket,
            actor=created_by,
            kind=TicketEvent.Kind.CREATED,
            to_status=ticket.status,
            message="Complaint raised",
            created_at=now,
        )
    if safety_flag:
        for manager in managers():
            notify(
                manager,
                f"Safety issue reported: {ticket.code} {ticket.title} at {ticket.location}",
                ticket=ticket,
                kind=Reminder.Kind.SAFETY,
                auto_key=f"safety:{ticket.pk}:{manager.pk}",
            )
    return ticket, True


def refresh_priority(ticket, now=None) -> bool:
    """Re-score a running complaint so aging (half SLA / overdue) raises its priority."""
    if not ticket.sla_due_at:
        return False
    score, band, _ = priority.calculate_ticket_priority(
        severity=ticket.severity,
        safety_flag=ticket.safety_flag,
        additional_affected_people=ticket.affected_people,
        is_critical_location=priority.is_critical_location(ticket.location),
        has_recurrence=ticket.is_recurrence,
        created_at=ticket.sla_due_at - timedelta(hours=ticket.sla_hours),
        sla_hours=ticket.sla_hours,
        total_paused_seconds=ticket.total_paused_seconds(now),
    )
    if score != ticket.priority_score or band != ticket.priority_band:
        Ticket.objects.filter(pk=ticket.pk).update(priority_score=score, priority_band=band)
        ticket.priority_score, ticket.priority_band = score, band
        return True
    return False


# ---------------------------------------------------------------------------
# Notifications & reminders
# ---------------------------------------------------------------------------


def _email(reminder):
    if not getattr(settings, "EMAIL_NOTIFICATIONS", False) or not reminder.recipient.email:
        return
    try:
        send_mail(
            subject=f"[FixIt] {reminder.get_kind_display()}",
            message=reminder.message,
            from_email=None,
            recipient_list=[reminder.recipient.email],
            fail_silently=True,
        )
    except Exception:  # never let mail problems break the request
        logger.exception("Failed to email reminder %s", reminder.pk)


def notify(recipient, message, *, ticket=None, kind=Reminder.Kind.UPDATE, created_by=None,
           auto_key=None, due_at=None):
    """Create an in-app reminder/notification. Automatic ones are de-duplicated by auto_key."""
    if recipient is None or not recipient.is_active:
        return None
    if created_by is not None and recipient.pk == created_by.pk and kind != Reminder.Kind.MANUAL:
        return None
    values = {
        "recipient": recipient,
        "created_by": created_by,
        "ticket": ticket,
        "kind": kind,
        "message": message[:500],
        "due_at": due_at or clock.now(),
        "created_at": clock.now(),
    }
    try:
        if auto_key:
            with transaction.atomic():
                reminder, created = Reminder.objects.get_or_create(auto_key=auto_key, defaults=values)
            if not created:
                return None
        else:
            reminder = Reminder.objects.create(**values)
    except IntegrityError:
        return None
    if reminder.due_at <= clock.now():
        _email(reminder)
    return reminder


def reminder_recipient_options(ticket, user) -> list[tuple[str, str]]:
    """Who the user may send a reminder to from a complaint page."""
    options = []
    if ticket.assigned_to and ticket.assigned_to_id != user.id:
        options.append(("worker", f"Assigned worker ({ticket.assigned_to.display_name})"))
    if ticket.created_by and ticket.created_by_id != user.id:
        options.append(("requester", f"Requester ({ticket.created_by.display_name})"))
    if not user.has_feature(F.MANAGE_COMPLAINTS) or ticket.assigned_to is None:
        options.append(("managers", "Maintenance admins"))
    options.append(("self", "Myself (personal reminder)"))
    return options


def send_ticket_reminder(ticket, sender, target, message, due_at=None):
    """Send a manual reminder about a complaint. Returns the number of reminders created."""
    now = clock.now()
    recent = Reminder.objects.filter(
        ticket=ticket,
        created_by=sender,
        kind=Reminder.Kind.MANUAL,
        created_at__gte=now - timedelta(minutes=MANUAL_REMINDER_COOLDOWN_MINUTES),
    ).exclude(recipient=sender)
    if target != "self" and recent.exists():
        raise ValueError(
            f"You already sent a reminder in the last {MANUAL_REMINDER_COOLDOWN_MINUTES} minutes."
        )

    if target == "worker":
        recipients = [ticket.assigned_to]
    elif target == "requester":
        recipients = [ticket.created_by]
    elif target == "managers":
        recipients = managers()
    elif target == "self":
        recipients = [sender]
    else:
        raise ValueError("Choose who should get the reminder.")
    recipients = [r for r in recipients if r is not None and (r.pk != sender.pk or target == "self")]
    if not recipients:
        raise ValueError("Nobody to remind yet.")

    text = message.strip() or f"Reminder about {ticket.code}: {ticket.title}"
    created = 0
    for recipient in recipients:
        if notify(recipient, text, ticket=ticket, kind=Reminder.Kind.MANUAL, created_by=sender,
                  due_at=due_at):
            created += 1
    if target != "self":
        names = ", ".join(r.display_name for r in recipients)
        TicketEvent.objects.create(
            ticket=ticket,
            actor=sender,
            kind=TicketEvent.Kind.REMINDER,
            message=f"Reminder sent to {names}: {text}",
            created_at=now,
        )
    return created


def unread_reminder_count(user) -> int:
    if not user.is_authenticated:
        return 0
    return Reminder.objects.filter(recipient=user, is_done=False, due_at__lte=clock.now()).count()


# ---------------------------------------------------------------------------
# Hooks after a status change
# ---------------------------------------------------------------------------


def after_transition(ticket, user, old_status, new_status, now):
    from apps.payments.services import create_job_payment

    S = Ticket.Status
    requester = ticket.created_by
    worker = ticket.assigned_to

    if new_status == S.ASSIGNED and worker:
        notify(worker, f"New job: {ticket.code} {ticket.title} at {ticket.location}",
               ticket=ticket, kind=Reminder.Kind.NEW_JOB, created_by=user)
        notify(requester, f"{ticket.code} was assigned to {worker.display_name}.",
               ticket=ticket, created_by=user)
    elif new_status == S.IN_PROGRESS:
        notify(requester, f"Work has started on {ticket.code}.", ticket=ticket, created_by=user)
    elif new_status == S.WAITING_ACCESS:
        notify(requester, f"The worker could not access the room for {ticket.code}. "
               "Please make sure someone is available.", ticket=ticket, created_by=user)
    elif new_status == S.WAITING_PARTS:
        notify(requester, f"{ticket.code} is waiting for spare parts.", ticket=ticket,
               created_by=user)
    elif new_status == S.REPORTED_FIXED:
        notify(requester, f"{ticket.code} was reported fixed. Please check and confirm, "
               "or reopen it if it is not fixed.", ticket=ticket,
               kind=Reminder.Kind.CONFIRM_FIX, created_by=user)
    elif new_status == S.VERIFIED_FIXED:
        payment = create_job_payment(ticket)
        if payment and worker:
            notify(worker, f"{ticket.code} was confirmed fixed. ₹{payment.amount} added to your "
                   "earnings.", ticket=ticket, created_by=user)
    elif new_status == S.REOPENED:
        for recipient in [worker, *managers()]:
            notify(recipient, f"{ticket.code} was reopened: not fixed.", ticket=ticket,
                   created_by=user)
    elif new_status in (S.REJECTED, S.CANCELLED, S.MERGED, S.CLOSED_UNVERIFIED):
        notify(requester, f"{ticket.code} is now {ticket.get_status_display().lower()}.",
               ticket=ticket, created_by=user)

    # Automatic reminders are pointless once the SLA stops
    if new_status in (S.REPORTED_FIXED, S.VERIFIED_FIXED, S.CLOSED_UNVERIFIED, S.CANCELLED,
                      S.REJECTED, S.MERGED):
        Reminder.objects.filter(
            ticket=ticket,
            is_done=False,
            kind__in=[Reminder.Kind.SLA_HALF, Reminder.Kind.SLA_OVERDUE, Reminder.Kind.UNASSIGNED],
        ).update(is_done=True, done_at=now)


# ---------------------------------------------------------------------------
# Due-task monitor (auto-close, SLA reminders, aging)
# ---------------------------------------------------------------------------


def run_due_tasks(force=False) -> int:
    """Evaluate time-based rules. Runs lazily (at most once a minute) from middleware."""
    from apps.tickets import workflow

    if not force and not cache.add("fixit:due-tasks", 1, DUE_TASKS_INTERVAL_SECONDS):
        return 0

    now = clock.now()
    changes = 0

    for ticket in Ticket.objects.filter(
        status=Ticket.Status.REPORTED_FIXED, reported_fixed_at__lte=now - timedelta(hours=72)
    ):
        try:
            workflow.perform_transition(ticket, None, Ticket.Status.CLOSED_UNVERIFIED)
            changes += 1
        except workflow.TransitionError:
            logger.warning("Auto-close failed for %s", ticket.code)

    admin_team = managers()

    for ticket in Ticket.objects.filter(
        status__in=[Ticket.Status.SUBMITTED, Ticket.Status.TRIAGED],
        assigned_to__isnull=True,
        created_at__lte=now - timedelta(hours=UNASSIGNED_REMINDER_HOURS),
    ):
        for manager in admin_team:
            if notify(manager, f"{ticket.code} has waited over {UNASSIGNED_REMINDER_HOURS} hours "
                      "for a worker.", ticket=ticket, kind=Reminder.Kind.UNASSIGNED,
                      auto_key=f"unassigned:{ticket.pk}:{ticket.reopen_count}:{manager.pk}"):
                changes += 1

    running = Ticket.objects.filter(status__in=RUNNING_STATUSES).select_related(
        "location__building", "assigned_to"
    )
    for ticket in running:
        remaining = ticket.sla_remaining_seconds(now)
        if remaining is None:
            continue
        workers = [ticket.assigned_to] if ticket.assigned_to else []
        if remaining < 0:
            for recipient in workers + admin_team:
                if notify(recipient, f"{ticket.code} is overdue ({ticket.priority_band}, "
                          f"{ticket.sla_hours}h SLA): {ticket.title}", ticket=ticket,
                          kind=Reminder.Kind.SLA_OVERDUE,
                          auto_key=f"overdue:{ticket.pk}:{ticket.reopen_count}:{recipient.pk}"):
                    changes += 1
        elif remaining <= ticket.sla_hours * 3600 / 2:
            for recipient in workers:
                if notify(recipient, f"Half of the SLA time for {ticket.code} is used up. "
                          "Please prioritise it.", ticket=ticket, kind=Reminder.Kind.SLA_HALF,
                          auto_key=f"half:{ticket.pk}:{ticket.reopen_count}:{recipient.pk}"):
                    changes += 1
        if refresh_priority(ticket, now):
            changes += 1

    for ticket in Ticket.objects.filter(
        status=Ticket.Status.REPORTED_FIXED,
        reported_fixed_at__lte=now - timedelta(hours=CONFIRM_REMINDER_HOURS),
    ):
        if notify(ticket.created_by, f"Please confirm whether {ticket.code} is fixed. It closes "
                  "automatically 72 hours after the fix was reported.", ticket=ticket,
                  kind=Reminder.Kind.CONFIRM_FIX,
                  auto_key=f"confirm:{ticket.pk}:{ticket.reopen_count}"):
            changes += 1

    return changes
