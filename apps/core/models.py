from django.db import models


class DemoClock(models.Model):
    """Single-row table holding simulated clock offset in seconds for DEMO_MODE."""

    offset_seconds = models.FloatField(default=0.0)

    class Meta:
        verbose_name = "Demo Clock"
        verbose_name_plural = "Demo Clock"

    def __str__(self) -> str:
        return f"DemoClock(offset={self.offset_seconds}s)"
