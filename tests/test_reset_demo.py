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


def test_reset_demo_creates_three_distinct_users(settings, db):
    settings.DEMO_MODE = True

    # Pre-clean or setup
    User.objects.all().delete()

    call_command("reset_demo", "--yes")

    demo_users = list(User.objects.filter(username__in=[
        "requester_demo", "technician_demo", "admin_demo"
    ]))
    assert len(demo_users) == 3

    roles = {u.role for u in demo_users}
    assert roles == {User.Role.REQUESTER, User.Role.TECHNICIAN, User.Role.ADMIN}

    for u in demo_users:
        assert u.check_password("DemoFixItPass123!") is True
