import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models import F as Col
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts import features as F
from apps.accounts.decorators import feature_required
from apps.accounts.models import User
from apps.core import clock
from apps.payments import services
from apps.payments.forms import MarkPaidForm, PaymentEditForm, PaymentForm
from apps.payments.models import WorkerPayment


def _filtered(request, qs):
    params = request.GET
    if params.get("status") in WorkerPayment.Status.values:
        qs = qs.filter(status=params["status"])
    if params.get("kind") in WorkerPayment.Kind.values:
        qs = qs.filter(kind=params["kind"])
    if params.get("worker", "").isdigit():
        qs = qs.filter(worker_id=int(params["worker"]))
    month = params.get("month", "")
    if len(month) == 7 and month[4] == "-" and month.replace("-", "").isdigit():
        year, mon = int(month[:4]), int(month[5:])
        if 1 <= mon <= 12:
            qs = qs.filter(created_at__year=year, created_at__month=mon)
    q = params.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(worker_name__icontains=q) | Q(description__icontains=q) | Q(reference__icontains=q)
        )
    return qs


@feature_required(F.WORKER_PAYMENTS, F.OWN_PAYMENTS)
def payment_list(request):
    user = request.user
    manage = user.has_feature(F.WORKER_PAYMENTS)
    base = WorkerPayment.objects.select_related("worker", "ticket")
    if not manage:
        base = base.filter(worker=user)
    qs = _filtered(request, base)

    if manage and request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fixit-worker-payments.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["Date", "Worker", "Type", "Complaint", "Description", "Amount", "Status", "Method",
             "Reference", "Paid at"]
        )
        for p in qs:
            writer.writerow([
                p.created_at.date(), p.worker_name, p.get_kind_display(),
                p.ticket.code if p.ticket else "", p.description, p.amount, p.get_status_display(),
                p.get_method_display(), p.reference, p.paid_at or "",
            ])
        return response

    now = clock.now()
    month_qs = base.filter(paid_at__year=now.year, paid_at__month=now.month,
                           status=WorkerPayment.Status.PAID)
    summary = services.totals(base)
    summary["paid_this_month"] = month_qs.aggregate(total=Sum("amount"))["total"] or 0

    per_worker = []
    if manage:
        per_worker = (
            WorkerPayment.objects.exclude(status=WorkerPayment.Status.CANCELLED)
            .values("worker_id", "worker_name")
            .annotate(
                pending=Sum("amount", filter=Q(status=WorkerPayment.Status.PENDING)),
                paid=Sum("amount", filter=Q(status=WorkerPayment.Status.PAID)),
                jobs=Count("id", filter=Q(kind=WorkerPayment.Kind.JOB)),
            )
            .order_by(Col("pending").desc(nulls_last=True), "worker_name")
        )

    summary["workers_owed"] = sum(1 for row in per_worker if row["pending"])

    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "payments/list.html", {
        "manage": manage,
        "page": page,
        "payments": page.object_list,
        "summary": summary,
        "per_worker": per_worker,
        "workers": User.objects.filter(role=User.Role.WORKER).order_by("first_name") if manage else [],
        "statuses": WorkerPayment.Status.choices,
        "kinds": WorkerPayment.Kind.choices,
        "methods": WorkerPayment.Method.choices,
        "filters": request.GET,
    })


@feature_required(F.WORKER_PAYMENTS)
def payment_create(request):
    initial = {}
    if request.GET.get("worker", "").isdigit():
        initial["worker"] = int(request.GET["worker"])
    form = PaymentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        payment.created_by = request.user
        payment.created_at = clock.now()
        payment.save()
        if form.cleaned_data.get("pay_now"):
            services.mark_paid(
                payment, method=form.cleaned_data["method"],
                reference=form.cleaned_data.get("reference", ""), paid_by=request.user,
            )
        messages.success(request, f"Payment of ₹{payment.amount} recorded for {payment.worker_name}.")
        return redirect("payments:list")
    return render(request, "payments/form.html", {"form": form, "title": "Record a payment"})


@feature_required(F.WORKER_PAYMENTS)
def payment_edit(request, pk):
    payment = get_object_or_404(WorkerPayment, pk=pk)
    if payment.status != WorkerPayment.Status.PENDING:
        messages.error(request, "Only pending payments can be edited.")
        return redirect("payments:list")
    form = PaymentEditForm(request.POST or None, instance=payment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Payment updated.")
        return redirect("payments:list")
    return render(request, "payments/form.html", {
        "form": form, "title": f"Edit payment for {payment.worker_name}", "payment": payment,
    })


@require_POST
@feature_required(F.WORKER_PAYMENTS)
def payment_mark_paid(request, pk):
    payment = get_object_or_404(WorkerPayment, pk=pk, status=WorkerPayment.Status.PENDING)
    form = MarkPaidForm(request.POST)
    if form.is_valid():
        services.mark_paid(
            payment, method=form.cleaned_data["method"],
            reference=form.cleaned_data.get("reference", ""), paid_by=request.user,
        )
        messages.success(request, f"₹{payment.amount} marked as paid to {payment.worker_name}.")
    else:
        messages.error(request, "Choose a payment method.")
    return redirect(request.POST.get("next") if request.POST.get("next", "").startswith("/")
                    and not request.POST.get("next", "").startswith("//") else "payments:list")


@require_POST
@feature_required(F.WORKER_PAYMENTS)
def payment_pay_all(request, worker_id):
    worker = get_object_or_404(User, pk=worker_id)
    form = MarkPaidForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a payment method.")
        return redirect("payments:list")
    pending = WorkerPayment.objects.filter(worker=worker, status=WorkerPayment.Status.PENDING)
    total = pending.aggregate(total=Sum("amount"))["total"] or 0
    count = 0
    for payment in pending:
        services.mark_paid(
            payment, method=form.cleaned_data["method"],
            reference=form.cleaned_data.get("reference", ""), paid_by=request.user,
        )
        count += 1
    messages.success(request, f"Paid {count} pending item(s), ₹{total}, to {worker.display_name}.")
    return redirect("payments:list")


@require_POST
@feature_required(F.WORKER_PAYMENTS)
def payment_cancel(request, pk):
    payment = get_object_or_404(WorkerPayment, pk=pk, status=WorkerPayment.Status.PENDING)
    payment.status = WorkerPayment.Status.CANCELLED
    payment.save(update_fields=["status"])
    messages.success(request, "Payment cancelled.")
    return redirect("payments:list")
