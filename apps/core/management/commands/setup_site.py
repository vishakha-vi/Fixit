from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = (
        "Idempotent deploy step: create the admin from ADMIN_EMAIL/ADMIN_PASSWORD and, when "
        "DEMO_MODE is on and the database has no complaints yet, load the demo campus."
    )

    def handle(self, *args, **options):
        call_command("ensure_admin", stdout=self.stdout)
        if getattr(settings, "DEMO_MODE", False):
            if Ticket.objects.exists():
                self.stdout.write("Demo data already present; nothing to seed.")
            else:
                call_command("reset_demo", "--yes", "--if-empty", stdout=self.stdout)
        else:
            self.stdout.write("DEMO_MODE is off; no demo data loaded.")
