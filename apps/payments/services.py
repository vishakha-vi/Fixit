from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum

from apps.core import clock
from apps.payments.models import WorkerPayment


def create_job_payment(ticket):
    """Record a pending payment for the worker once a fix is verified (one per complaint)."""
    worker = ticket.assigned_to
    if worker is None:
        return None
    existing = WorkerPayment.objects.filter(ticket=ticket, kind=WorkerPayment.Kind.JOB).first()
    if existing:
        return existing
    amount = (worker.rate_per_job or Decimal("0")) + (ticket.material_cost or Decimal("0"))
    description = f"{ticket.code} {ticket.title}"
    if ticket.material_cost:
        description += f" (incl. ₹{ticket.material_cost} materials)"
    try:
        with transaction.atomic():
            return WorkerPayment.objects.create(
                worker=worker,
                ticket=ticket,
                kind=WorkerPayment.Kind.JOB,
                amount=amount,
                description=description[:255],
                created_at=clock.now(),
            )
    except IntegrityError:
        return WorkerPayment.objects.filter(ticket=ticket, kind=WorkerPayment.Kind.JOB).first()


def mark_paid(payment, *, method, reference="", paid_by=None):
    payment.status = WorkerPayment.Status.PAID
    payment.method = method
    payment.reference = reference.strip()
    payment.paid_at = clock.now()
    if paid_by and not payment.created_by:
        payment.created_by = paid_by
    payment.save()
    return payment


def totals(queryset) -> dict:
    zero = Decimal("0")
    agg = queryset.aggregate(
        pending=Sum("amount", filter=Q(status=WorkerPayment.Status.PENDING)),
        paid=Sum("amount", filter=Q(status=WorkerPayment.Status.PAID)),
        pending_count=Count("id", filter=Q(status=WorkerPayment.Status.PENDING)),
        paid_count=Count("id", filter=Q(status=WorkerPayment.Status.PAID)),
    )
    return {
        "pending": agg["pending"] or zero,
        "paid": agg["paid"] or zero,
        "pending_count": agg["pending_count"] or 0,
        "paid_count": agg["paid_count"] or 0,
    }
