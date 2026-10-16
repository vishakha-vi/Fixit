import os

from django.core.management.base import BaseCommand

from apps.accounts import features as F
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create (or update) the main admin account from ADMIN_EMAIL / ADMIN_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", ""))
        parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""))
        parser.add_argument("--name", default=os.environ.get("ADMIN_NAME", "FixIt Admin"))
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Also reset the password if the admin already exists.",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        password = options["password"] or ""
        if not email or not password:
            self.stdout.write("ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin creation.")
            return

        user = User.objects.filter(email__iexact=email).first() or User.objects.filter(
            username__iexact=email
        ).first()
        created = user is None
        if created:
            first, _, last = options["name"].partition(" ")
            user = User(username=email, email=email, first_name=first, last_name=last)
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.features = list(F.ALL_FEATURE_CODES)
        if created or options["reset_password"]:
            user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Admin {'created' if created else 'updated'}: {email}"
        ))
