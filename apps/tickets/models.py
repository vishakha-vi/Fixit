import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core import clock


def generate_completion_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class Ticket(models.Model):
    """A maintenance complaint raised by a student or staff member."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        TRIAGED = "TRIAGED", "Reviewed by admin"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        WAITING_PARTS = "WAITING_PARTS", "Waiting for parts"
        WAITING_ACCESS = "WAITING_ACCESS", "Waiting for access"
        REPORTED_FIXED = "REPORTED_FIXED", "Reported fixed - awaiting confirmation"
        VERIFIED_FIXED = "VERIFIED_FIXED", "Confirmed fixed"
        REOPENED = "REOPENED", "Reopened"
        CLOSED_UNVERIFIED = "CLOSED_UNVERIFIED", "Closed - not confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"
        MERGED = "MERGED", "Merged"

    class Category(models.TextChoices):
        ELECTRICAL = "electrical", "Electrical"
        PLUMBING = "plumbing", "Plumbing / Water"
        CARPENTRY = "carpentry", "Carpentry / Furniture"
        HOUSEKEEPING = "housekeeping", "Cleaning / Housekeeping"
        NETWORK = "network", "Internet / Wi-Fi"
        HVAC = "hvac", "AC / Fan / Ventilation"
        CIVIL = "civil", "Civil / Painting / Walls"
        PEST = "pest", "Pest control"
        OTHER = "other", "Other"

    class Severity(models.TextChoices):
        MINOR = "minor", "Minor - inconvenience"
        MODERATE = "moderate", "Moderate - partly unusable"
        MAJOR = "major", "Major - not usable"
        CRITICAL = "critical", "Critical - emergency"

    class VerifiedMethod(models.TextChoices):
        REQUESTER_CONFIRM = "requester_confirm", "Confirmed by requester"
        ON_SITE_CODE = "on_site_code", "On-site completion code"

    OPEN_STATUSES = [
        Status.SUBMITTED,
        Status.TRIAGED,
        Status.ASSIGNED,
        Status.IN_PROGRESS,
        Status.WAITING_PARTS,
        Status.WAITING_ACCESS,
        Status.REPORTED_FIXED,
        Status.REOPENED,
    ]
    ACTIVE_WORK_STATUSES = [
        Status.ASSIGNED,
        Status.IN_PROGRESS,
        Status.WAITING_PARTS,
        Status.WAITING_ACCESS,
        Status.REOPENED,
    ]

    title = models.CharField(max_length=150)
    description = models.TextField(max_length=4000)
    category = models.CharField(max_length=20, choices=Category.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MODERATE)
    safety_flag = models.BooleanField(
        default=False, help_text="Danger to people (exposed wires, gas smell, flooding...)"
    )
    affected_people = models.PositiveIntegerField(
        default=0, help_text="Other people affected besides the reporter"
    )
    location = models.ForeignKey(
        "locations.Location", on_delete=models.PROTECT, related_name="tickets"
    )
    location_detail = models.CharField(max_length=200, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="tickets_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_assigned",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )

    priority_score = models.PositiveIntegerField(default=0)
    priority_band = models.CharField(max_length=2, default="P4", db_index=True)
    is_recurrence = models.BooleanField(default=False)

    sla_hours = models.PositiveIntegerField(default=168)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.FloatField(default=0.0)
    paused_since = models.DateTimeField(null=True, blank=True)
    sla_stopped_at = models.DateTimeField(null=True, blank=True)

    completion_code = models.CharField(max_length=6, default=generate_completion_code)
    work_notes = models.TextField(blank=True)
    material_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    access_attempts = models.PositiveIntegerField(default=0)
    reopen_count = models.PositiveIntegerField(default=0)
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_tickets"
    )

    reported_fixed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_method = models.CharField(max_length=20, choices=VerifiedMethod.choices, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=clock.now, db_index=True)
    updated_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority_band"])]

    def save(self, *args, **kwargs):
        self.updated_at = clock.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} {self.title}"

    @property
    def code(self) -> str:
        return f"FIX-{self.pk:05d}" if self.pk else "FIX-NEW"

    def get_absolute_url(self) -> str:
        return reverse("tickets:detail", args=[self.pk])

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    @property
    def is_paused(self) -> bool:
        return self.paused_since is not None

    # ---- SLA ---------------------------------------------------------
    def total_paused_seconds(self, now=None) -> float:
        total = self.paused_seconds
        if self.paused_since:
            total += ((now or clock.now()) - self.paused_since).total_seconds()
        return total

    def effective_due_at(self, now=None):
        if not self.sla_due_at:
            return None
        return self.sla_due_at + timedelta(seconds=self.total_paused_seconds(now))

    def sla_remaining_seconds(self, now=None):
        due = self.effective_due_at(now)
        if due is None:
            return None
        reference = self.sla_stopped_at or now or clock.now()
        return (due - reference).total_seconds()

    @property
    def is_overdue(self) -> bool:
        remaining = self.sla_remaining_seconds()
        return remaining is not None and remaining < 0 and self.is_open

    @property
    def resolution_hours(self):
        end = self.verified_at or self.closed_at
        if not end:
            return None
        return round((end - self.created_at).total_seconds() / 3600, 1)


class TicketEvent(models.Model):
    """Audit trail entry shown in the complaint timeline."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status", "Status change"
        ASSIGNED = "assigned", "Assigned"
        REASSIGNED = "reassigned", "Reassigned"
        COMMENT = "comment", "Comment"
        REMINDER = "reminder", "Reminder"
        SYSTEM = "system", "System"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.ticket.code} {self.kind} {self.to_status}".strip()


class Reminder(models.Model):
    """In-app reminder; created by users or automatically by the SLA monitor."""

    class Kind(models.TextChoices):
        MANUAL = "manual", "Reminder"
        NEW_JOB = "new_job", "New job assigned"
        UPDATE = "update", "Complaint update"
        UNASSIGNED = "unassigned", "Waiting for assignment"
        SLA_HALF = "sla_half", "Half of SLA time used"
        SLA_OVERDUE = "sla_overdue", "SLA overdue"
        CONFIRM_FIX = "confirm_fix", "Please confirm the fix"
        SAFETY = "safety", "Safety issue"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminders"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reminders_sent",
    )
    ticket = models.ForeignKey(
        Ticket, null=True, blank=True, on_delete=models.CASCADE, related_name="reminders"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.MANUAL)
    message = models.CharField(max_length=500)
    due_at = models.DateTimeField(default=clock.now, db_index=True)
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    auto_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["is_done", "-due_at"]

    def __str__(self) -> str:
        return f"Reminder to {self.recipient}: {self.message[:40]}"

    @property
    def is_due(self) -> bool:
        return not self.is_done and self.due_at <= clock.now()
