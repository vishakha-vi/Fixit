from datetime import datetime, timedelta

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils import timezone


def _get_demo_clock():
    from apps.core.models import DemoClock

    try:
        clock, _ = DemoClock.objects.get_or_create(id=1, defaults={"offset_seconds": 0.0})
        return clock
    except (OperationalError, ProgrammingError):
        # Database might not be migrated yet
        return None


def now() -> datetime:
    """Return current timestamp.

    When DEMO_MODE is False: returns the standard timezone.now().
    When DEMO_MODE is True: returns timezone.now() plus the persisted DemoClock offset.
    """
    if getattr(settings, "DEMO_MODE", False):
        clock = _get_demo_clock()
        if clock and clock.offset_seconds:
            return timezone.now() + timedelta(seconds=clock.offset_seconds)
    return timezone.now()


def advance(delta: timedelta) -> datetime:
    """Advance the simulated demo clock by a given timedelta.

    Raises RuntimeError if DEMO_MODE is False.
    """
    if not getattr(settings, "DEMO_MODE", False):
        raise RuntimeError("Clock cannot be advanced when DEMO_MODE is disabled.")

    clock = _get_demo_clock()
    if clock is None:
        raise RuntimeError("DemoClock model is not accessible. Run migrations first.")

    clock.offset_seconds += delta.total_seconds()
    clock.save()
    return now()


def reset() -> datetime:
    """Reset the simulated demo clock offset back to zero.

    Raises RuntimeError if DEMO_MODE is False.
    """
    if not getattr(settings, "DEMO_MODE", False):
        raise RuntimeError("Clock cannot be reset when DEMO_MODE is disabled.")

    clock = _get_demo_clock()
    if clock is None:
        raise RuntimeError("DemoClock model is not accessible. Run migrations first.")

    clock.offset_seconds = 0.0
    clock.save()
    return now()
