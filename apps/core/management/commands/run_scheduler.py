from django.core.management.base import BaseCommand

from apps.tickets.services import run_due_tasks


class Command(BaseCommand):
    help = "Evaluate time-based rules now (auto-close, SLA reminders, priority aging). Cron-friendly."

    def handle(self, *args, **options):
        changes = run_due_tasks(force=True)
        self.stdout.write(self.style.SUCCESS(f"Due tasks evaluated: {changes} change(s)."))
