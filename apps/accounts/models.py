from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts import features as F


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"
        WORKER = "worker", "Worker"
        ADMIN = "admin", "Admin"

    class Availability(models.TextChoices):
        ON_DUTY = "on_duty", "On duty"
        OFF_DUTY = "off_duty", "Off duty"
        ON_LEAVE = "on_leave", "On leave"

    class Specialty(models.TextChoices):
        GENERAL = "general", "General maintenance"
        ELECTRICAL = "electrical", "Electrical"
        PLUMBING = "plumbing", "Plumbing"
        CARPENTRY = "carpentry", "Carpentry"
        HOUSEKEEPING = "housekeeping", "Housekeeping"
        NETWORK = "network", "Internet / Wi-Fi"
        HVAC = "hvac", "AC / Ventilation"
        CIVIL = "civil", "Civil / Painting"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Role determining permissions and access rights in FixIt",
    )
    features = models.JSONField(
        default=list,
        blank=True,
        help_text="Feature codes this user may use (admins always have all features)",
    )
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(
        max_length=120,
        blank=True,
        help_text="Department, course or hostel room (students and staff)",
    )

    # Worker-only details
    specialty = models.CharField(
        max_length=20, choices=Specialty.choices, default=Specialty.GENERAL, blank=True
    )
    area = models.ForeignKey(
        "locations.Building",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="area_workers",
        help_text="Home area / building the worker normally covers",
    )
    rate_per_job = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("250.00"),
        help_text="Amount paid to the worker for each verified fix (₹)",
    )
    availability = models.CharField(
        max_length=20, choices=Availability.choices, default=Availability.ON_DUTY
    )
    current_location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="present_workers",
        help_text="Where the worker last reported being",
    )
    last_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["first_name", "last_name", "username"]

    # ---- roles -------------------------------------------------------
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    def is_staff_member(self) -> bool:
        return self.role == self.Role.STAFF

    def is_worker(self) -> bool:
        return self.role == self.Role.WORKER

    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    # ---- feature access ---------------------------------------------
    def has_feature(self, code: str) -> bool:
        if not self.is_active:
            return False
        if self.is_admin_role():
            return True
        return code in (self.features or [])

    @property
    def feature_set(self) -> set[str]:
        if self.is_admin_role():
            return set(F.ALL_FEATURE_CODES)
        return set(self.features or [])

    def apply_role_defaults(self) -> None:
        self.features = F.default_features_for_role(self.role)

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.email or self.username

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"
