"""Small helpers to build FixIt objects in tests."""

from decimal import Decimal

from apps.accounts.models import User
from apps.locations.models import Building, Location
from apps.tickets import services

PASSWORD = "TestSecretPassword123!"


def make_user(username, role, **extra):
    user = User(username=username, email=f"{username}@test.campus.edu", role=role,
                first_name=username.title(), **extra)
    user.apply_role_defaults()
    if role == User.Role.ADMIN:
        user.is_staff = user.is_superuser = True
    user.set_password(PASSWORD)
    user.save()
    return user


def make_location(building="Hostel A", room="Room 101", critical=False):
    b, _ = Building.objects.get_or_create(name=building, defaults={"code": building[:3].upper() + str(Building.objects.count())})
    loc, _ = Location.objects.get_or_create(building=b, name=room, defaults={"is_critical": critical})
    return loc


def make_ticket(requester, location=None, **overrides):
    data = {
        "title": "Ceiling fan not working",
        "description": "The fan in my room stopped working yesterday.",
        "category": "electrical",
        "severity": "moderate",
        "location": location or make_location(),
        "safety_flag": False,
        "affected_people": 0,
    }
    data.update(overrides)
    ticket, _ = services.create_ticket(created_by=requester, **data)
    return ticket


def campus():
    """A typical cast: admin, staff, two students, two workers."""
    return {
        "admin": make_user("admin1", User.Role.ADMIN),
        "staff": make_user("staff1", User.Role.STAFF),
        "student": make_user("student1", User.Role.STUDENT),
        "other_student": make_user("student2", User.Role.STUDENT),
        "worker": make_user("worker1", User.Role.WORKER, rate_per_job=Decimal("300")),
        "other_worker": make_user("worker2", User.Role.WORKER),
    }
