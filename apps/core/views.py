import uuid

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.core import clock


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
    """FixIt landing home page."""
    context = {
        "version": getattr(settings, "APP_VERSION", "0.1.0"),
        "demo_mode": getattr(settings, "DEMO_MODE", False),
    }
    return render(request, "home.html", context)


def custom_404_view(request, exception=None):
    """User-friendly 404 page."""
    return render(request, "404.html", status=404)


def custom_500_view(request):
    """User-friendly 500 page that never leaks stack traces."""
    reference_id = uuid.uuid4().hex[:8].upper()
    return render(request, "500.html", {"reference_id": reference_id}, status=500)
