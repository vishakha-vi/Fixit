import uuid

from django.conf import settings
from django.db import connection
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render

from apps.accounts import features as F
from apps.accounts.decorators import feature_required
from apps.accounts.forms import WorkerLocationForm
from apps.core import clock
from apps.locations.models import Building
from apps.payments.models import WorkerPayment
from apps.tickets import services, stats
from apps.tickets.models import Reminder, Ticket


def healthz_view(request):
    """Health check endpoint returning DB connectivity, version, demo mode status, and current time."""
    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_ok = True
    except Exception:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "error",
        "db": db_ok,
        "version": getattr(settings, "APP_VERSION", "0.1.0"),
        "demo_mode": getattr(settings, "DEMO_MODE", False),
        "time": clock.now().isoformat(),
    }
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


def home_view(request):
    """Landing page for visitors; a personal overview for signed-in users."""
    user = request.user
    if not user.is_authenticated:
        return render(request, "home.html", {})

    visible = services.visible_tickets(user)
    context = {"is_home": True}

    mine = visible.filter(created_by=user)
    if (user.has_feature(F.SUBMIT_COMPLAINT) or user.has_feature(F.TRACK_COMPLAINT)) and (
        not user.is_admin_role() or mine.exists()
    ):
        context["my"] = {
            "open": mine.filter(status__in=Ticket.OPEN_STATUSES).count(),
            "awaiting": mine.filter(status=Ticket.Status.REPORTED_FIXED),
            "resolved": mine.filter(status=Ticket.Status.VERIFIED_FIXED).count(),
            "recent": mine.order_by("-updated_at")[:6],
        }

    if user.has_feature(F.WORK_ON_COMPLAINTS) and not user.is_admin_role():
        jobs = visible.filter(assigned_to=user)
        now = clock.now()
        context["jobs"] = {
            "active": jobs.filter(status__in=Ticket.ACTIVE_WORK_STATUSES).order_by(
                "-priority_score", "sla_due_at"
            ),
            "awaiting": jobs.filter(status=Ticket.Status.REPORTED_FIXED).count(),
            "done_month": jobs.filter(
                status=Ticket.Status.VERIFIED_FIXED,
                verified_at__year=now.year,
                verified_at__month=now.month,
            ).count(),
            "pending_pay": WorkerPayment.objects.filter(
                worker=user, status=WorkerPayment.Status.PENDING
            ).aggregate(total=Sum("amount"))["total"] or 0,
        }
        context["location_form"] = WorkerLocationForm(initial={
            "current_location": user.current_location_id,
            "availability": user.availability,
        })

    if user.has_feature(F.MANAGE_COMPLAINTS):
        open_qs = Ticket.objects.filter(status__in=Ticket.OPEN_STATUSES)
        context["manage"] = {
            "needs_action": open_qs.filter(
                status__in=[Ticket.Status.SUBMITTED, Ticket.Status.TRIAGED, Ticket.Status.REOPENED]
            ).select_related("location__building", "created_by").order_by("-priority_score")[:8],
            "unassigned": open_qs.filter(assigned_to__isnull=True).count(),
            "overdue": sum(1 for t in open_qs if t.is_overdue),
            "safety": open_qs.filter(safety_flag=True).count(),
        }

    if user.has_feature(F.REMINDERS):
        context["reminders"] = Reminder.objects.filter(
            recipient=user, is_done=False, due_at__lte=clock.now()
        ).select_related("ticket")[:5]

    return render(request, "home.html", context)


@feature_required(F.DASHBOARD)
def dashboard_view(request):
    period = request.GET.get("period", "30")
    if period not in dict(stats.PERIODS):
        period = "30"
    building = request.GET.get("building", "")
    building_id = int(building) if building.isdigit() else None
    data = stats.dashboard_stats(period, building_id)
    return render(request, "core/dashboard.html", {
        "s": data,
        "periods": stats.PERIODS,
        "period": period,
        "period_label": dict(stats.PERIODS)[period],
        "buildings": Building.objects.order_by("name"),
        "building": building,
        "recent": Ticket.objects.filter(Q(location__building_id=building_id) if building_id else Q())
        .select_related("location__building", "assigned_to")
        .order_by("-created_at")[:8],
    })


def custom_403_view(request, exception=None):
    """Friendly page when a user lacks access to a feature."""
    return render(request, "403.html", status=403)


def custom_404_view(request, exception=None):
    """User-friendly 404 page."""
    return render(request, "404.html", status=404)


def custom_500_view(request):
    """User-friendly 500 page that never leaks stack traces."""
    reference_id = uuid.uuid4().hex[:8].upper()
    return render(request, "500.html", {"reference_id": reference_id}, status=500)
