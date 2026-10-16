"""Admin portal: manage every account, feature access, campus areas and the demo clock."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts import features as F
from apps.accounts.decorators import admin_required
from apps.accounts.forms import BuildingForm, LocationForm, PortalUserForm, generate_password
from apps.accounts.models import User
from apps.core import clock
from apps.locations.models import Building, Location
from apps.payments.models import WorkerPayment
from apps.payments.services import totals
from apps.tickets.models import Reminder, Ticket, TicketEvent
from apps.tickets.services import run_due_tasks


@admin_required
def portal_home(request):
    role_counts = dict(User.objects.values_list("role").annotate(n=Count("id")))
    open_qs = Ticket.objects.filter(status__in=Ticket.OPEN_STATUSES)
    context = {
        "role_counts": [(value, label, role_counts.get(value, 0)) for value, label in User.Role.choices],
        "user_total": sum(role_counts.values()),
        "inactive_users": User.objects.filter(is_active=False).count(),
        "open_tickets": open_qs.count(),
        "unassigned": open_qs.filter(assigned_to__isnull=True).count(),
        "awaiting": open_qs.filter(status=Ticket.Status.REPORTED_FIXED).count(),
        "payments": totals(WorkerPayment.objects.all()),
        "buildings": Building.objects.count(),
        "locations": Location.objects.count(),
        "recent_users": User.objects.order_by("-date_joined")[:6],
        "recent_events": TicketEvent.objects.select_related("ticket", "actor").order_by(
            "-created_at", "-id"
        )[:10],
    }
    return render(request, "portal/home.html", context)


@admin_required
def user_list(request):
    qs = User.objects.select_related("area").annotate(
        raised=Count("tickets_created", distinct=True),
        assigned=Count("tickets_assigned", distinct=True),
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
            | Q(username__icontains=q) | Q(phone__icontains=q) | Q(department__icontains=q)
        )
    role = request.GET.get("role", "")
    if role in User.Role.values:
        qs = qs.filter(role=role)
    status = request.GET.get("status", "")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    qs = qs.order_by("role", "first_name", "last_name", "username")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "portal/users.html", {
        "page": page,
        "users": page.object_list,
        "roles": User.Role.choices,
        "filters": {"q": q, "role": role, "status": status},
        "feature_labels": F.FEATURE_LABELS,
    })


def _form_context(form, title, target=None):
    return {
        "form": form,
        "title": title,
        "target": target,
        "role_defaults": F.ROLE_DEFAULT_FEATURES,
        "feature_rows": F.FEATURES,
    }


@admin_required
def user_create(request):
    initial = {}
    if request.GET.get("role") in User.Role.values:
        initial["role"] = request.GET["role"]
    form = PortalUserForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if form.generated_password:
            messages.success(
                request,
                f"Account created for {user.email}. Temporary password: {form.generated_password} "
                "(share it with the user; it is shown only once).",
            )
        else:
            messages.success(request, f"Account created for {user.email}.")
        return redirect("portal:user_detail", pk=user.pk)
    return render(request, "portal/user_form.html", _form_context(form, "Create account"))


@admin_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = PortalUserForm(
        request.POST or None, instance=target, editing_self=(target.pk == request.user.pk)
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved changes for {target.email or target.username}.")
        return redirect("portal:user_detail", pk=target.pk)
    return render(
        request, "portal/user_form.html", _form_context(form, f"Edit {target.display_name}", target)
    )


@admin_required
def user_detail(request, pk):
    target = get_object_or_404(User.objects.select_related("area", "current_location"), pk=pk)
    raised = Ticket.objects.filter(created_by=target).select_related("location__building")
    assigned = Ticket.objects.filter(assigned_to=target).select_related("location__building")
    payments = WorkerPayment.objects.filter(worker=target).select_related("ticket")
    context = {
        "target": target,
        "features": [(code, label, target.has_feature(code)) for code, label, _ in F.FEATURES],
        "raised": raised[:20],
        "raised_count": raised.count(),
        "assigned": assigned[:20],
        "assigned_count": assigned.count(),
        "completed_count": assigned.filter(status=Ticket.Status.VERIFIED_FIXED).count(),
        "payments": payments[:20],
        "payment_totals": totals(payments),
        "reminders": Reminder.objects.filter(recipient=target).select_related("ticket")[:10],
        "activity": TicketEvent.objects.filter(actor=target).select_related("ticket").order_by(
            "-created_at", "-id"
        )[:15],
    }
    return render(request, "portal/user_detail.html", context)


@admin_required
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account.")
        return redirect("portal:user_detail", pk=pk)
    impact = {
        "raised": Ticket.objects.filter(created_by=target).count(),
        "assigned_open": Ticket.objects.filter(
            assigned_to=target, status__in=Ticket.OPEN_STATUSES
        ).count(),
        "payments_pending": WorkerPayment.objects.filter(
            worker=target, status=WorkerPayment.Status.PENDING
        ).aggregate(total=Sum("amount"))["total"] or 0,
    }
    if request.method == "POST":
        label = target.email or target.username
        try:
            target.delete()
        except ProtectedError:
            messages.error(request, "This account is still referenced by records and cannot be deleted. "
                           "Deactivate it instead.")
            return redirect("portal:user_detail", pk=pk)
        messages.success(request, f"Account {label} deleted. Their complaint and payment records are kept.")
        return redirect("portal:users")
    return render(request, "portal/user_delete.html", {"target": target, "impact": impact})


@admin_required
def user_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = SetPasswordForm(target, request.POST or None)
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-control"
    if request.method == "POST":
        if request.POST.get("generate"):
            new_password = generate_password()
            target.set_password(new_password)
            target.save(update_fields=["password"])
            messages.success(
                request, f"New password for {target.email or target.username}: {new_password}"
            )
            return redirect("portal:user_detail", pk=pk)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password updated for {target.email or target.username}.")
            return redirect("portal:user_detail", pk=pk)
    return render(request, "portal/user_password.html", {"target": target, "form": form})


@require_POST
@admin_required
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        messages.success(
            request, f"{target.display_name} is now {'active' if target.is_active else 'deactivated'}."
        )
    return redirect("portal:user_detail", pk=pk)


@require_POST
@admin_required
def user_reset_features(request, pk):
    target = get_object_or_404(User, pk=pk)
    target.apply_role_defaults()
    target.save(update_fields=["features"])
    messages.success(request, f"Feature access reset to {target.get_role_display()} defaults.")
    return redirect("portal:user_detail", pk=pk)


@admin_required
def role_defaults_json(request):
    return JsonResponse(F.ROLE_DEFAULT_FEATURES)


# ---------------------------------------------------------------------------
# Campus areas
# ---------------------------------------------------------------------------


@admin_required
def areas(request):
    building_form = BuildingForm(prefix="b")
    location_form = LocationForm(prefix="l")
    if request.method == "POST":
        if request.POST.get("form") == "building":
            building_form = BuildingForm(request.POST, prefix="b")
            if building_form.is_valid():
                building = building_form.save()
                messages.success(request, f"Building {building.name} added.")
                return redirect("portal:areas")
        elif request.POST.get("form") == "location":
            location_form = LocationForm(request.POST, prefix="l")
            if location_form.is_valid():
                location = location_form.save()
                messages.success(request, f"{location.full_name} added.")
                return redirect("portal:areas")

    buildings = Building.objects.annotate(
        open_count=Count(
            "locations__tickets",
            filter=Q(locations__tickets__status__in=Ticket.OPEN_STATUSES),
            distinct=True,
        ),
        worker_count=Count("area_workers", distinct=True),
    ).prefetch_related("locations").order_by("name")
    return render(request, "portal/areas.html", {
        "buildings": buildings,
        "building_form": building_form,
        "location_form": location_form,
    })


@require_POST
@admin_required
def area_delete(request, kind, pk):
    model = Building if kind == "building" else Location
    obj = get_object_or_404(model, pk=pk)
    try:
        obj.delete()
        messages.success(request, f"{obj} deleted.")
    except ProtectedError:
        messages.error(request, f"{obj} has complaints on record, so it cannot be deleted.")
    return redirect("portal:areas")


# ---------------------------------------------------------------------------
# Demo clock (only when DEMO_MODE is on)
# ---------------------------------------------------------------------------


@require_POST
@admin_required
def demo_clock(request):
    if not getattr(settings, "DEMO_MODE", False):
        messages.error(request, "Demo mode is off.")
        return redirect("portal:home")
    action = request.POST.get("action", "")
    if action == "reset":
        clock.reset()
        messages.success(request, "Demo clock reset to real time.")
    else:
        hours = {"1h": 1, "24h": 24, "72h": 72}.get(action)
        if hours:
            clock.advance(timedelta(hours=hours))
            messages.success(request, f"Demo clock moved forward {hours} hour(s).")
    changes = run_due_tasks(force=True)
    if changes:
        messages.info(request, f"Time-based rules applied: {changes} update(s).")
    target = request.POST.get("next", "")
    return redirect(target if target.startswith("/") and not target.startswith("//") else "portal:home")
