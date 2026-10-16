from django.conf import settings
from django.db import models

from apps.core import clock


class WorkerPayment(models.Model):
    """Money owed or paid to a worker: per verified job, salary, bonus or adjustment."""

    class Kind(models.TextChoices):
        JOB = "job", "Job payment"
        SALARY = "salary", "Salary"
        BONUS = "bonus", "Bonus"
        ADJUSTMENT = "adjustment", "Adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    class Method(models.TextChoices):
        UPI = "upi", "UPI"
        BANK = "bank", "Bank transfer"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"

    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    worker_name = models.CharField(
        max_length=150, blank=True, help_text="Snapshot kept if the worker account is deleted"
    )
    ticket = models.ForeignKey(
        "tickets.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.JOB)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    method = models.CharField(max_length=20, choices=Method.choices, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="UPI / bank reference no.")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
    )
    created_at = models.DateTimeField(default=clock.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=models.Q(kind="job"),
                name="one_job_payment_per_ticket",
            )
        ]

    def save(self, *args, **kwargs):
        if self.worker and not self.worker_name:
            self.worker_name = self.worker.display_name
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"₹{self.amount} to {self.worker_name or 'worker'} ({self.get_status_display()})"
