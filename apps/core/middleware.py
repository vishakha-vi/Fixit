import logging

from apps.tickets.services import run_due_tasks

logger = logging.getLogger(__name__)


class DueTasksMiddleware:
    """Lazily evaluates time-based rules (auto-close, SLA reminders) at most once a minute."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            try:
                run_due_tasks()
            except Exception:  # background housekeeping must never break a page
                logger.exception("Due-task evaluation failed")
        return self.get_response(request)
