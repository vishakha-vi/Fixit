import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User


def test_reset_demo_refuses_without_demo_mode(settings):
    settings.DEMO_MODE = False
    with pytest.raises(CommandError, match="DEMO_MODE is disabled"):
        call_command("reset_demo", "--yes")


def test_reset_demo_refuses_without_yes_flag(settings):
    settings.DEMO_MODE = True
    with pytest.raises(CommandError, match="--yes flag is required"):
        call_command("reset_demo")


def test_reset_demo_creates_demo_users_for_every_role(settings, db):
    settings.DEMO_MODE = True

    # Pre-clean or setup
    User.objects.all().delete()

    call_command("reset_demo", "--yes", "--users-only")

    demo_users = list(User.objects.filter(username__in=[
        "student_demo", "staff_demo", "worker_demo", "admin_demo"
    ]))
    assert len(demo_users) == 4

    roles = {u.role for u in demo_users}
    assert roles == {User.Role.STUDENT, User.Role.STAFF, User.Role.WORKER, User.Role.ADMIN}

    for u in demo_users:
        assert u.check_password("DemoFixItPass123!") is True


def test_reset_demo_seeds_sample_complaints(settings, db):
    from apps.tickets.models import Ticket

    settings.DEMO_MODE = True
    call_command("reset_demo", "--yes")
    assert Ticket.objects.count() > 30
    assert Ticket.objects.filter(status=Ticket.Status.VERIFIED_FIXED).exists()
    # demo clock is back to real time after seeding
    from apps.core.models import DemoClock
    assert DemoClock.objects.get(id=1).offset_seconds == 0.0

    # --if-empty does nothing once complaints exist
    before = Ticket.objects.count()
    call_command("reset_demo", "--yes", "--if-empty")
    assert Ticket.objects.count() == before
