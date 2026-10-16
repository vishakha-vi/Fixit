from django.db import models

from apps.core import clock


class Building(models.Model):
    """Campus building or facility."""

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    is_critical = models.BooleanField(
        default=False,
        help_text="Designated critical building (e.g. Health Center, Main Lab, Campus Dining)",
    )
    created_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Location(models.Model):
    """Specific room, space, or common area within a campus building."""

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(max_length=120, help_text="Room number, wing, or area identifier")
    floor = models.IntegerField(default=0, help_text="Floor number (0 for Ground Floor)")
    is_critical = models.BooleanField(
        default=False,
        help_text="Designated critical zone e.g. medical room, lab, entrance, mess",
    )
    is_common_area = models.BooleanField(
        default=False,
        help_text="Common area accessible to multiple residents/students",
    )
    created_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["building", "name"]
        unique_together = ("building", "name")

    @property
    def full_name(self) -> str:
        return f"{self.building.name} - {self.name}"

    def effective_is_critical(self) -> bool:
        return self.is_critical or self.building.is_critical

    def __str__(self) -> str:
        return self.full_name
