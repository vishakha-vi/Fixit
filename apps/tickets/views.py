from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts import features as F
from apps.accounts.decorators import feature_required
from apps.accounts.models import User
from apps.core import clock
from apps.locations.models import Building
from apps.tickets import services, workflow
from apps.tickets.forms import CommentForm, PersonalReminderForm, TicketForm, TicketReminderForm
from apps.tickets.models import Reminder, Ticket, TicketEvent

LIST_FEATURES = (
    F.TRACK_COMPLAINT,
    F.SUBMIT_COMPLAINT,
    F.VIEW_ALL_COMPLAINTS,
    F.MANAGE_COMPLAINTS,
    F.WORK_ON_COMPLAINTS,
)

PROGRESS_STEPS = [
    ("SUBMITTED", "Submitted"),
    ("TRIAGED", "Reviewed"),
    ("ASSIGNED", "Worker assigned"),
    ("IN_PROGRESS", "Work in progress"),
    ("REPORTED_FIXED", "Reported fixed"),
    ("VERIFIED_FIXED", "Confirmed fixed"),
]
STEP_INDEX = {
    "SUBMITTED": 0,
    "TRIAGED": 1,
    "ASSIGNED": 2,
    "REOPENED": 2,
    "IN_PROGRESS": 3,
    "WAITING_PARTS": 3,
    "WAITING_ACCESS": 3,
    "REPORTED_FIXED": 4,
    "VERIFIED_FIXED": 5,
    "CLOSED_UNVERIFIED": 5,
}

STATUS_GROUPS = {
    "open": Ticket.OPEN_STATUSES,
    "needs_action": [Ticket.Status.SUBMITTED, Ticket.Status.TRIAGED, Ticket.Status.REOPENED],
    "in_progress": [
        Ticket.Status.ASSIGNED,
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.WAITING_PARTS,
        Ticket.Status.WAITING_ACCESS,
    ],
    "awaiting_confirmation": [Ticket.Status.REPORTED_FIXED],
    "resolved": [Ticket.Status.VERIFIED_FIXED],
    "closed": [
        Ticket.Status.VERIFIED_FIXED,
        Ticket.Status.CLOSED_UNVERIFIED,
        Ticket.Status.CANCELLED,
        Ticket.Status.REJECTED,
        Ticket.Status.MERGED,
    ],
}
SORTS = {
    "newest": ["-created_at"],
    "oldest": ["created_at"],
    "priority": ["-priority_score", "created_at"],
    "due": ["sla_due_at"],
}


def parse_ticket_code(value: str):
    value = (value or "").strip().upper()
    if value.startswith("FIX-"):
        value = value[4:]
    elif value.startswith("FIX"):
        value = value[3:]
    value = value.lstrip("#")
    return int(value) if value.isdigit() else None


def _safe_next(request, default="tickets:reminders"):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(default)


def _aware(dt):
    if dt is not None and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


# ---------------------------------------------------------------------------
# List / create / track
# ---------------------------------------------------------------------------


@feature_required(*LIST_FEATURES)
def ticket_list(request):
    user = request.user
    qs = services.visible_tickets(user)
    params = request.GET

    q = params.get("q", "").strip()
    if q:
        code = parse_ticket_code(q)
        cond = Q(title__icontains=q) | Q(description__icontains=q) | Q(
            location__name__icontains=q
        ) | Q(location__building__name__icontains=q)
        if code:
            cond |= Q(pk=code)
        qs = qs.filter(cond)

    group = params.get("group", "open")
    if group in STATUS_GROUPS:
        qs = qs.filter(status__in=STATUS_GROUPS[group])
    elif group in Ticket.Status.values:
        qs = qs.filter(status=group)

    for field in ("category", "priority_band"):
        value = params.get(field)
        if value:
            qs = qs.filter(**{field: value})
    if params.get("building", "").isdigit():
        qs = qs.filter(location__building_id=int(params["building"]))

    scope = params.get("scope", "")
    if scope == "mine":
        qs = qs.filter(created_by=user)
    elif scope == "my_jobs":
        qs = qs.filter(assigned_to=user)
    elif scope == "unassigned":
        qs = qs.filter(assigned_to__isnull=True)
    elif scope == "overdue":
        qs = [t for t in qs.filter(status__in=Ticket.OPEN_STATUSES) if t.is_overdue]
    if params.get("worker", "").isdigit():
        if isinstance(qs, list):
            qs = [t for t in qs if t.assigned_to_id == int(params["worker"])]
        else:
            qs = qs.filter(assigned_to_id=int(params["worker"]))

    sort = params.get("sort", "newest")
    if not isinstance(qs, list):
        qs = qs.order_by(*SORTS.get(sort, SORTS["newest"]))

    page = Paginator(qs, 20).get_page(params.get("page"))
    context = {
        "page": page,
        "tickets": page.object_list,
        "filters": {
            "q": q,
            "group": group,
            "category": params.get("category", ""),
            "priority_band": params.get("priority_band", ""),
            "building": params.get("building", ""),
            "scope": scope,
            "sort": sort,
        },
        "groups": [
            ("open", "Open"),
            ("needs_action", "Needs action"),
            ("in_progress", "In progress"),
            ("awaiting_confirmation", "Awaiting confirmation"),
            ("resolved", "Confirmed fixed"),
            ("closed", "Closed"),
            ("all", "All"),
        ],
        "categories": Ticket.Category.choices,
        "buildings": Building.objects.order_by("name"),
        "can_see_all": user.has_feature(F.VIEW_ALL_COMPLAINTS)
        or user.has_feature(F.MANAGE_COMPLAINTS),
    }
    return render(request, "tickets/list.html", context)


@feature_required(F.SUBMIT_COMPLAINT)
def ticket_create(request):
    form = TicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        ticket, created = services.create_ticket(
            created_by=request.user,
            title=data["title"],
            description=data["description"],
            category=data["category"],
            severity=data["severity"],
            location=data["location"],
            location_detail=data.get("location_detail", ""),
            safety_flag=data.get("safety_flag", False),
            affected_people=data.get("affected_people") or 0,
        )
        if created:
            messages.success(
                request,
                f"Complaint {ticket.code} submitted. Priority {ticket.priority_band}, "
                f"target fix time {ticket.sla_hours} hours.",
            )
            if ticket.safety_flag:
                messages.warning(
                    request,
                    "Safety issue flagged: the maintenance team has been alerted. If anyone is in "
                    "danger, move away and call campus security now.",
                )
        else:
            messages.info(request, f"You already submitted this complaint as {ticket.code}.")
        return redirect(ticket)
    return render(request, "tickets/form.html", {"form": form})


@feature_required(*LIST_FEATURES)
def track(request):
    code_text = request.GET.get("code", "").strip()
    ticket = None
    not_found = False
    if code_text:
        code = parse_ticket_code(code_text)
        ticket = services.visible_tickets(request.user).filter(pk=code).first() if code else None
        if ticket:
            return redirect(ticket)
        not_found = True
    recent = services.visible_tickets(request.user).filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
    ).order_by("-updated_at")[:8]
    return render(
        request,
        "tickets/track.html",
        {"code": code_text, "not_found": not_found, "recent": recent},
    )


# ---------------------------------------------------------------------------
# Detail & actions
# ---------------------------------------------------------------------------


def _get_visible_ticket(request, pk):
    # IDOR rule: tickets the user may not see are reported as 404, never 403
    return get_object_or_404(services.visible_tickets(request.user), pk=pk)


@feature_required(*LIST_FEATURES)
def ticket_detail(request, pk):
    ticket = _get_visible_ticket(request, pk)
    user = request.user
    events = ticket.events.select_related("actor").all()

    reached = {}
    for event in events:
        if event.to_status and event.to_status not in reached:
            reached[event.to_status] = event.created_at
    current_index = STEP_INDEX.get(ticket.status, -1)
    steps = []
    for index, (status, label) in enumerate(PROGRESS_STEPS):
        steps.append({
            "label": label,
            "done": index <= current_index,
            "current": index == current_index,
            "time": reached.get(status),
        })

    participates = services.can_participate(ticket, user)
    actions = workflow.available_actions(ticket, user)
    needs_workers = any(a["to"] == "ASSIGNED" for a in actions) or workflow.can_reassign(
        ticket, user
    )
    workers = []
    if needs_workers:
        counts = services.open_job_counts()
        for worker in services.active_workers():
            worker.open_jobs = counts.get(worker.pk, 0)
            worker.same_area = bool(worker.area_id and worker.area_id == ticket.location.building_id)
            workers.append(worker)
        workers.sort(key=lambda w: (not w.same_area, w.availability != "on_duty", w.open_jobs))

    can_remind = user.has_feature(F.REMINDERS) and participates and ticket.is_open
    context = {
        "ticket": ticket,
        "events": events,
        "steps": steps,
        "off_track": ticket.status in ("CANCELLED", "REJECTED", "MERGED"),
        "actions": actions,
        "workers": workers,
        "can_reassign": workflow.can_reassign(ticket, user),
        "can_comment": participates,
        "comment_form": CommentForm(),
        "can_remind": can_remind,
        "reminder_form": TicketReminderForm(
            target_choices=services.reminder_recipient_options(ticket, user)
        ) if can_remind else None,
        # Only the requester sees the code; otherwise staff could bypass resident confirmation
        "show_code": ticket.created_by_id == user.id,
        "similar": services.similar_open_tickets(ticket)
        if user.has_feature(F.MANAGE_COMPLAINTS) and ticket.is_open else [],
        "payment": ticket.payments.filter(kind="job").first()
        if user.has_feature(F.WORKER_PAYMENTS) or ticket.assigned_to_id == user.id else None,
    }
    return render(request, "tickets/detail.html", context)


@require_POST
@feature_required(*LIST_FEATURES)
def ticket_action(request, pk):
    ticket = _get_visible_ticket(request, pk)
    to_status = request.POST.get("to", "")
    post = request.POST
    data = {
        "reason": post.get("reason", "")[:1000],
        "work_notes": post.get("work_notes", "")[:2000],
        "material_cost": post.get("material_cost", ""),
        "checklist": post.get("checklist") == "on",
        "code": post.get("code", "").strip(),
    }
    if post.get("assignee", "").isdigit():
        data["assignee"] = User.objects.filter(pk=int(post["assignee"]), is_active=True).first()
    if post.get("target"):
        target_pk = parse_ticket_code(post["target"])
        data["target"] = (
            services.visible_tickets(request.user).filter(pk=target_pk).first() if target_pk else None
        )

    try:
        ticket = workflow.perform_transition(
            ticket, request.user, to_status, data, expected_status=post.get("from_status") or None
        )
        messages.success(request, f"{ticket.code} is now: {ticket.get_status_display()}.")
        if to_status == Ticket.Status.REPORTED_FIXED and data["code"]:
            try:
                ticket = workflow.perform_transition(
                    ticket, request.user, Ticket.Status.VERIFIED_FIXED, {"code": data["code"]}
                )
                messages.success(request, "Completion code accepted: fix verified on site.")
            except workflow.TransitionError as exc:
                messages.warning(request, f"Reported fixed, but the code was not accepted: {exc}")
    except workflow.TransitionError as exc:
        messages.error(request, str(exc))
    return redirect(ticket)


@require_POST
@feature_required(F.MANAGE_COMPLAINTS)
def ticket_reassign(request, pk):
    ticket = _get_visible_ticket(request, pk)
    assignee = None
    if request.POST.get("assignee", "").isdigit():
        assignee = User.objects.filter(pk=int(request.POST["assignee"])).first()
    try:
        workflow.reassign(ticket, request.user, assignee, request.POST.get("reason", "")[:500])
        messages.success(request, f"{ticket.code} reassigned to {assignee.display_name}.")
    except workflow.TransitionError as exc:
        messages.error(request, str(exc))
    return redirect(ticket)


@require_POST
@feature_required(*LIST_FEATURES)
def ticket_comment(request, pk):
    ticket = _get_visible_ticket(request, pk)
    if not services.can_participate(ticket, request.user):
        messages.error(request, "You can view this complaint but not comment on it.")
        return redirect(ticket)
    form = CommentForm(request.POST)
    if form.is_valid():
        TicketEvent.objects.create(
            ticket=ticket,
            actor=request.user,
            kind=TicketEvent.Kind.COMMENT,
            message=form.cleaned_data["message"].strip(),
            created_at=clock.now(),
        )
        for recipient in {ticket.created_by, ticket.assigned_to} - {None, request.user}:
            services.notify(
                recipient,
                f"New comment on {ticket.code} from {request.user.display_name}",
                ticket=ticket,
                created_by=request.user,
            )
        messages.success(request, "Comment added.")
    else:
        messages.error(request, "Comment cannot be empty.")
    return redirect(ticket)


@require_POST
@feature_required(F.REMINDERS)
def ticket_remind(request, pk):
    ticket = _get_visible_ticket(request, pk)
    if not services.can_participate(ticket, request.user):
        messages.error(request, "You cannot send reminders for this complaint.")
        return redirect(ticket)
    form = TicketReminderForm(
        request.POST, target_choices=services.reminder_recipient_options(ticket, request.user)
    )
    if form.is_valid():
        try:
            count = services.send_ticket_reminder(
                ticket,
                request.user,
                form.cleaned_data["target"],
                form.cleaned_data.get("message", ""),
                due_at=_aware(form.cleaned_data.get("remind_at")),
            )
            messages.success(request, f"Reminder scheduled ({count} recipient{'s' if count != 1 else ''}).")
        except ValueError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Please choose who should get the reminder.")
    return redirect(ticket)


# ---------------------------------------------------------------------------
# Reminders inbox
# ---------------------------------------------------------------------------


@feature_required(F.REMINDERS)
def reminder_list(request):
    user = request.user
    now = clock.now()
    tab = request.GET.get("tab", "due")
    base = Reminder.objects.filter(recipient=user).select_related("ticket", "created_by")
    tabs = {
        "due": base.filter(is_done=False, due_at__lte=now).order_by("-due_at"),
        "upcoming": base.filter(is_done=False, due_at__gt=now).order_by("due_at"),
        "done": base.filter(is_done=True).order_by("-done_at")[:100],
        "sent": Reminder.objects.filter(created_by=user, kind=Reminder.Kind.MANUAL)
        .exclude(recipient=user)
        .select_related("ticket", "recipient")
        .order_by("-created_at")[:100],
    }
    if tab not in tabs:
        tab = "due"

    form = PersonalReminderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.notify(
            user,
            form.cleaned_data["message"],
            kind=Reminder.Kind.MANUAL,
            created_by=user,
            due_at=_aware(form.cleaned_data["remind_at"]),
        )
        messages.success(request, "Personal reminder saved.")
        return redirect("tickets:reminders")

    counts = {
        "due": tabs["due"].count(),
        "upcoming": tabs["upcoming"].count(),
    }
    return render(
        request,
        "tickets/reminders.html",
        {"tab": tab, "items": tabs[tab], "counts": counts, "form": form},
    )


@require_POST
@feature_required(F.REMINDERS)
def reminder_done(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, recipient=request.user)
    reminder.is_done = not reminder.is_done
    reminder.done_at = clock.now() if reminder.is_done else None
    reminder.save(update_fields=["is_done", "done_at"])
    return _safe_next(request)


@require_POST
@feature_required(F.REMINDERS)
def reminder_all_done(request):
    Reminder.objects.filter(
        recipient=request.user, is_done=False, due_at__lte=clock.now()
    ).update(is_done=True, done_at=clock.now())
    messages.success(request, "All due reminders marked as done.")
    return redirect("tickets:reminders")


@require_POST
@login_required
def reminder_delete(request, pk):
    reminder = get_object_or_404(
        Reminder, Q(recipient=request.user) | Q(created_by=request.user), pk=pk
    )
    reminder.delete()
    messages.success(request, "Reminder deleted.")
    return _safe_next(request)
