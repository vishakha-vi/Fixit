import logging

from django.conf import settings

from apps.accounts import features as F
from apps.core import clock
from apps.tickets.services import unread_reminder_count

logger = logging.getLogger(__name__)


def fixit(request):
    user = getattr(request, "user", None)
    context = {
        "version": getattr(settings, "APP_VERSION", "0.1.0"),
        "demo_mode": getattr(settings, "DEMO_MODE", False),
        "allow_signup": getattr(settings, "ALLOW_STUDENT_SIGNUP", True),
        "demo_show_credentials": getattr(settings, "DEMO_SHOW_CREDENTIALS", False),
    }
    if context["demo_mode"]:
        try:
            context["demo_now"] = clock.now()
        except Exception:  # error pages must render even when the database is down
            logger.exception("Could not read demo clock")
    if user is None or not user.is_authenticated:
        return context

    has = user.has_feature
    context["nav"] = {
        "dashboard": has(F.DASHBOARD),
        "submit": has(F.SUBMIT_COMPLAINT),
        "complaints": any(
            has(c)
            for c in (F.TRACK_COMPLAINT, F.VIEW_ALL_COMPLAINTS, F.MANAGE_COMPLAINTS,
                      F.WORK_ON_COMPLAINTS)
        ),
        "jobs_only": has(F.WORK_ON_COMPLAINTS) and not (
            has(F.VIEW_ALL_COMPLAINTS) or has(F.MANAGE_COMPLAINTS)
        ),
        "track": has(F.TRACK_COMPLAINT) or has(F.WORK_ON_COMPLAINTS) or has(F.VIEW_ALL_COMPLAINTS),
        "reminders": has(F.REMINDERS),
        "payments": has(F.WORKER_PAYMENTS) or has(F.OWN_PAYMENTS),
        "all_payments": has(F.WORKER_PAYMENTS),
        "locator": has(F.WORKER_LOCATOR),
        "admin": user.is_admin_role(),
    }
    try:
        context["due_reminders"] = unread_reminder_count(user) if has(F.REMINDERS) else 0
    except Exception:
        logger.exception("Could not count reminders")
        context["due_reminders"] = 0
    return context
