import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.core import clock


class Command(BaseCommand):
    help = "Reset demo clock and recreate standard demo users (requester, technician, admin)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirmation flag required to execute demo reset.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "DEMO_MODE", False):
            raise CommandError("Refusing to run: DEMO_MODE is disabled.")

        if not options.get("yes"):
            raise CommandError("Refusing to run: --yes flag is required.")

        # 1. Reset demo clock offset
        clock.reset()
        self.stdout.write(self.style.SUCCESS("Demo clock offset reset to 0.0s."))

        # 2. Get demo password from env
        demo_password = os.environ.get("DEMO_PASSWORD", "DemoFixItPass123!")

        demo_users_data = [
            {
                "username": "requester_demo",
                "email": "requester@demo.campus.edu",
                "first_name": "Rita",
                "last_name": "Requester",
                "role": User.Role.REQUESTER,
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "technician_demo",
                "email": "technician@demo.campus.edu",
                "first_name": "Tom",
                "last_name": "Technician",
                "role": User.Role.TECHNICIAN,
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "admin_demo",
                "email": "admin@demo.campus.edu",
                "first_name": "Alice",
                "last_name": "Admin",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        ]

        created_count = 0
        for data in demo_users_data:
            # Recreate user cleanly
            User.objects.filter(username=data["username"]).delete()
            user = User(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=data["role"],
                is_staff=data["is_staff"],
                is_superuser=data["is_superuser"],
            )
            user.set_password(demo_password)
            user.save()
            created_count += 1
            self.stdout.write(f"  Created demo user: {user.username} ({user.role})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully recreated {created_count} demo users. Demo password set."
            )
        )
