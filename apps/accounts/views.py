from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts import features as F
from apps.accounts.decorators import feature_required
from apps.accounts.forms import ProfileForm, SignupForm, WorkerLocationForm
from apps.accounts.models import User
from apps.core import clock
from apps.locations.models import Building
from apps.tickets.models import Ticket


def signup(request):
    if not getattr(settings, "ALLOW_STUDENT_SIGNUP", True):
        raise Http404("Self sign-up is disabled")
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(request, f"Welcome to FixIt, {user.first_name}! You can now raise complaints.")
        return redirect("home")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def profile(request):
    user = request.user
    profile_form = ProfileForm(instance=user)
    password_form = PasswordChangeForm(user)
    for field in password_form.fields.values():
        field.widget.attrs["class"] = "form-control"

    if request.method == "POST":
        if request.POST.get("form") == "password":
            password_form = PasswordChangeForm(user, request.POST)
            for field in password_form.fields.values():
                field.widget.attrs["class"] = "form-control"
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Password changed.")
                return redirect("accounts:profile")
        else:
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated.")
                return redirect("accounts:profile")

    return render(request, "accounts/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        "features": [(code, label, desc, user.has_feature(code)) for code, label, desc in F.FEATURES],
    })


@require_POST
@feature_required(F.WORK_ON_COMPLAINTS)
def update_my_location(request):
    form = WorkerLocationForm(request.POST)
    if form.is_valid():
        user = request.user
        user.current_location = form.cleaned_data.get("current_location")
        user.availability = form.cleaned_data["availability"]
        if form.cleaned_data.get("lat") is not None:
            user.last_lat = form.cleaned_data["lat"]
            user.last_lng = form.cleaned_data["lng"]
        user.location_updated_at = clock.now()
        user.save(update_fields=[
            "current_location", "availability", "last_lat", "last_lng", "location_updated_at"
        ])
        messages.success(request, "Your location and availability were updated.")
    else:
        messages.error(request, "Could not update location: " + "; ".join(
            str(e) for errors in form.errors.values() for e in errors
        ))
    target = request.POST.get("next", "")
    return redirect(target if target.startswith("/") and not target.startswith("//") else "home")


@feature_required(F.WORKER_LOCATOR)
def worker_locator(request):
    workers = list(
        User.objects.filter(role=User.Role.WORKER, is_active=True)
        .select_related("area", "current_location__building")
        .order_by("first_name", "last_name")
    )
    active_jobs = (
        Ticket.objects.filter(
            assigned_to__in=workers, status__in=Ticket.ACTIVE_WORK_STATUSES
        )
        .select_related("location__building")
        .order_by("-priority_score")
    )
    jobs_by_worker = {}
    for job in active_jobs:
        jobs_by_worker.setdefault(job.assigned_to_id, []).append(job)

    specialty = request.GET.get("specialty", "")
    building_filter = request.GET.get("building", "")
    status_filter = request.GET.get("status", "")

    rows = []
    for worker in workers:
        jobs = jobs_by_worker.get(worker.pk, [])
        current_job = next((j for j in jobs if j.status == Ticket.Status.IN_PROGRESS), None)
        if worker.availability != User.Availability.ON_DUTY:
            state = worker.availability
        elif current_job:
            state = "busy"
        else:
            state = "available"
        located = current_job.location if current_job else worker.current_location
        located_building = located.building if located else worker.area
        row = {
            "worker": worker,
            "jobs": jobs,
            "current_job": current_job,
            "state": state,
            "location": located,
            "building": located_building,
            "maps_url": (
                f"https://www.google.com/maps?q={worker.last_lat},{worker.last_lng}"
                if worker.last_lat is not None and worker.last_lng is not None else ""
            ),
        }
        if specialty and worker.specialty != specialty:
            continue
        if building_filter.isdigit() and (
            not located_building or located_building.pk != int(building_filter)
        ):
            continue
        if status_filter and state != status_filter:
            continue
        rows.append(row)

    groups = {}
    for row in rows:
        key = row["building"].name if row["building"] else "Location not shared"
        groups.setdefault(key, []).append(row)
    ordered_groups = sorted(groups.items(), key=lambda item: (item[0] == "Location not shared", item[0]))

    counts = {"available": 0, "busy": 0, "off_duty": 0, "on_leave": 0}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1

    return render(request, "workers/locator.html", {
        "groups": ordered_groups,
        "total": len(rows),
        "counts": counts,
        "specialties": User.Specialty.choices,
        "buildings": Building.objects.order_by("name"),
        "filters": {"specialty": specialty, "building": building_filter, "status": status_filter},
        "location_form": WorkerLocationForm(initial={
            "current_location": request.user.current_location_id,
            "availability": request.user.availability,
        }) if request.user.is_worker() else None,
    })
