from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import clock


def test_clock_demo_mode_false(settings):
    settings.DEMO_MODE = False

    t_real = timezone.now()
    t_clock = clock.now()
    assert abs((t_clock - t_real).total_seconds()) < 1.0

    with pytest.raises(RuntimeError, match="DEMO_MODE is disabled"):
        clock.advance(timedelta(hours=2))

    with pytest.raises(RuntimeError, match="DEMO_MODE is disabled"):
        clock.reset()


def test_clock_demo_mode_true(settings, db):
    settings.DEMO_MODE = True
    clock.reset()

    base_time = clock.now()
    clock.advance(timedelta(hours=5))
    advanced_time = clock.now()

    diff_seconds = (advanced_time - base_time).total_seconds()
    assert 17990 <= diff_seconds <= 18010  # 5 hours = 18000s

    clock.reset()
    reset_time = clock.now()
    real_now = timezone.now()
    assert abs((reset_time - real_now).total_seconds()) < 2.0
