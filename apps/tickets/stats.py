"""Aggregations for the complaints dashboard."""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.core import clock
from apps.payments.models import WorkerPayment
from apps.tickets.models import Ticket

PERIODS = [("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"),
           ("365", "Last 12 months"), ("all", "All time")]

BAND_ORDER = ["P1", "P2", "P3", "P4"]
BAND_LABELS = {"P1": "P1 Critical", "P2": "P2 High", "P3": "P3 Medium", "P4": "P4 Low"}


def _bars(rows, label_map=None, order=None):
    """Turn (key, count) rows into bar data with widths relative to the largest value."""
    rows = [(k, n) for k, n in rows if n]
    if order:
        index = {k: i for i, k in enumerate(order)}
        rows.sort(key=lambda r: index.get(r[0], len(index)))
    else:
        rows.sort(key=lambda r: -r[1])
    top = max((n for _, n in rows), default=0)
    return [
        {
            "key": k,
            "label": (label_map or {}).get(k, k or "Unknown"),
            "count": n,
            "width": round(100 * n / top, 1) if top else 0,
        }
        for k, n in rows
    ]


def _nice_max(value: int) -> int:
    if value <= 4:
        return 4
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        nice = step * magnitude
        if nice >= value:
            return int(nice) if nice >= 4 else 4
    return int(value)


def line_chart(labels, series, width=720, height=230):
    """Geometry for a small multi-series line chart rendered as inline SVG."""
    left, right, top, bottom = 34, 12, 12, 26
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = max((max(s["values"]) for s in series if s["values"]), default=0)
    y_max = _nice_max(peak)
    count = len(labels)

    def x_at(i):
        return left + (plot_w * i / (count - 1) if count > 1 else plot_w / 2)

    def y_at(v):
        return top + plot_h - plot_h * v / y_max

    ticks = [{"value": int(y_max * f), "y": round(y_at(y_max * f), 1)} for f in (0, 0.25, 0.5, 0.75, 1)]
    out_series = []
    for s in series:
        points = [(round(x_at(i), 1), round(y_at(v), 1)) for i, v in enumerate(s["values"])]
        out_series.append({
            **s,
            "points": " ".join(f"{x},{y}" for x, y in points),
            "area": (
                f"M{points[0][0]},{top + plot_h} "
                + " ".join(f"L{x},{y}" for x, y in points)
                + f" L{points[-1][0]},{top + plot_h} Z"
            ) if points else "",
            "last": {"x": points[-1][0], "y": points[-1][1], "value": s["values"][-1]} if points else None,
        })
    # Direct end labels only when they cannot collide with each other or the x-axis labels
    ends = [s["last"] for s in out_series if s["last"]]
    labels_fit = all(abs(a["y"] - b["y"]) >= 16 for i, a in enumerate(ends) for b in ends[i + 1:])
    for s in out_series:
        last = s["last"]
        if not last:
            continue
        above = last["y"] - 9
        below = last["y"] + 17
        if above >= top + 10:
            last["label_y"] = above
        elif below <= top + plot_h - 6:
            last["label_y"] = below
        else:
            last["label_y"] = None
        last["show_label"] = labels_fit and last["label_y"] is not None

    step = max(1, count // 7)
    x_labels = [
        {"x": round(x_at(i), 1), "text": labels[i]}
        for i in range(0, count, step)
    ]
    columns = [
        {
            "x": round(x_at(i), 1),
            "label": labels[i],
            "values": [s["values"][i] for s in series],
        }
        for i in range(count)
    ]
    return {
        "width": width,
        "height": height,
        "left": left,
        "right_x": width - right,
        "baseline": top + plot_h,
        "ticks": ticks,
        "series": out_series,
        "x_labels": x_labels,
        "columns": columns,
        "slot": plot_w / max(count - 1, 1),
    }


def dashboard_stats(period="30", building_id=None):
    now = clock.now()
    tickets = Ticket.objects.all()
    if building_id:
        tickets = tickets.filter(location__building_id=building_id)

    days = int(period) if period.isdigit() else None
    in_period = tickets.filter(created_at__gte=now - timedelta(days=days)) if days else tickets

    total = in_period.count()
    open_now = list(
        tickets.filter(status__in=Ticket.OPEN_STATUSES).select_related("location__building")
    )
    overdue = [t for t in open_now if t.is_overdue]
    today_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)

    resolved = list(
        in_period.filter(status=Ticket.Status.VERIFIED_FIXED).values_list(
            "created_at", "verified_at"
        )
    )
    hours = [(v - c).total_seconds() / 3600 for c, v in resolved if v]
    unverified = in_period.filter(status=Ticket.Status.CLOSED_UNVERIFIED).count()
    finished = len(resolved) + unverified

    status_labels = dict(Ticket.Status.choices)
    category_labels = dict(Ticket.Category.choices)

    by_status = _bars(
        in_period.values_list("status").annotate(n=Count("id")),
        status_labels,
        order=Ticket.Status.values,
    )
    by_category = _bars(in_period.values_list("category").annotate(n=Count("id")), category_labels)
    by_building = _bars(
        in_period.values_list("location__building__name").annotate(n=Count("id"))
    )
    by_band = _bars(
        in_period.values_list("priority_band").annotate(n=Count("id")), BAND_LABELS, BAND_ORDER
    )

    # Daily trend: raised vs confirmed fixed (max 30 days so the chart stays readable)
    trend_days = min(days or 30, 30)
    start_day = (timezone.localtime(now) - timedelta(days=trend_days - 1)).date()
    day_list = [start_day + timedelta(days=i) for i in range(trend_days)]
    raised = dict.fromkeys(day_list, 0)
    fixed = dict.fromkeys(day_list, 0)
    window_start = today_start - timedelta(days=trend_days - 1)
    for created in tickets.filter(created_at__gte=window_start).values_list("created_at", flat=True):
        day = timezone.localtime(created).date()
        if day in raised:
            raised[day] += 1
    for verified in tickets.filter(verified_at__gte=window_start).values_list("verified_at", flat=True):
        day = timezone.localtime(verified).date()
        if day in fixed:
            fixed[day] += 1
    trend = line_chart(
        [d.strftime("%d %b") for d in day_list],
        [
            {"name": "Raised", "slot": 1, "values": [raised[d] for d in day_list]},
            {"name": "Confirmed fixed", "slot": 2, "values": [fixed[d] for d in day_list]},
        ],
    )

    # Worker performance
    workers = list(User.objects.filter(role=User.Role.WORKER).select_related("area"))
    worker_rows = []
    pending_pay = dict(
        WorkerPayment.objects.filter(status=WorkerPayment.Status.PENDING)
        .values_list("worker_id")
        .annotate(total=Sum("amount"))
    )
    job_stats = {
        row["assigned_to"]: row
        for row in tickets.filter(assigned_to__isnull=False)
        .values("assigned_to")
        .annotate(
            open_jobs=Count("id", filter=Q(status__in=Ticket.ACTIVE_WORK_STATUSES)),
            reported=Count("id", filter=Q(status=Ticket.Status.REPORTED_FIXED)),
        )
    }
    done_hours = {}
    for worker_id, created, verified in in_period.filter(
        status=Ticket.Status.VERIFIED_FIXED, assigned_to__isnull=False
    ).values_list("assigned_to", "created_at", "verified_at"):
        done_hours.setdefault(worker_id, []).append((verified - created).total_seconds() / 3600)
    for worker in workers:
        stats = job_stats.get(worker.pk, {})
        completed = done_hours.get(worker.pk, [])
        worker_rows.append({
            "worker": worker,
            "open_jobs": stats.get("open_jobs", 0),
            "awaiting": stats.get("reported", 0),
            "completed": len(completed),
            "avg_hours": round(sum(completed) / len(completed), 1) if completed else None,
            "pending_pay": pending_pay.get(worker.pk, 0),
        })
    worker_rows.sort(key=lambda r: (-r["completed"], -r["open_jobs"]))

    return {
        "total": total,
        "today": tickets.filter(created_at__gte=today_start).count(),
        "open": len(open_now),
        "unassigned": sum(1 for t in open_now if t.assigned_to_id is None),
        "awaiting": sum(1 for t in open_now if t.status == Ticket.Status.REPORTED_FIXED),
        "overdue": len(overdue),
        "resolved": len(resolved),
        "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
        "verification_rate": round(100 * len(resolved) / finished) if finished else None,
        "safety_open": sum(1 for t in open_now if t.safety_flag),
        "by_status": by_status,
        "by_category": by_category,
        "by_building": by_building,
        "by_band": by_band,
        "trend": trend,
        "trend_days": trend_days,
        "workers": worker_rows,
        "overdue_list": sorted(overdue, key=lambda t: t.sla_remaining_seconds() or 0)[:8],
    }
