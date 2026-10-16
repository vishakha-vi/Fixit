from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core import clock
from apps.tickets.models import Ticket
from apps.tickets.workflow import status_color_class

register = template.Library()

BAND_CLASSES = {"P1": "danger", "P2": "warning", "P3": "primary", "P4": "secondary"}
BAND_NAMES = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}


@register.filter
def status_class(status):
    return status_color_class(status)


@register.filter
def status_label(status):
    return dict(Ticket.Status.choices).get(status, status)


@register.simple_tag
def status_badge(ticket):
    css = status_color_class(ticket.status)
    text = " text-dark" if css == "warning" else ""
    return format_html(
        '<span class="badge rounded-pill text-bg-{}{}">{}</span>',
        css,
        text,
        ticket.get_status_display(),
    )


@register.simple_tag
def band_badge(band):
    css = BAND_CLASSES.get(band, "secondary")
    text = " text-dark" if css == "warning" else ""
    return format_html(
        '<span class="badge text-bg-{}{}" title="{} priority">{}</span>',
        css,
        text,
        BAND_NAMES.get(band, ""),
        band,
    )


@register.filter
def band_name(band):
    return BAND_NAMES.get(band, band)


def _human_duration(seconds: float) -> str:
    seconds = abs(int(seconds))
    if seconds < 60:
        return "less than a minute"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


@register.filter
def timeago(value):
    """Relative time against the FixIt clock (respects the demo clock offset)."""
    if not value:
        return ""
    delta = (clock.now() - value).total_seconds()
    if abs(delta) < 60:
        return "just now"
    return f"{_human_duration(delta)} ago" if delta > 0 else f"in {_human_duration(delta)}"


@register.filter
def duration(seconds):
    if seconds in (None, ""):
        return ""
    return _human_duration(float(seconds))


@register.simple_tag
def sla_badge(ticket):
    remaining = ticket.sla_remaining_seconds()
    if remaining is None:
        return ""
    if ticket.sla_stopped_at:
        if remaining >= 0:
            return mark_safe('<span class="badge text-bg-light border">SLA met</span>')
        return mark_safe('<span class="badge text-bg-light border text-danger">SLA missed</span>')
    if ticket.is_paused:
        return mark_safe('<span class="badge text-bg-secondary">SLA paused</span>')
    if remaining < 0:
        return format_html(
            '<span class="badge text-bg-danger">Overdue {}</span>', _human_duration(remaining)
        )
    css = "warning text-dark" if remaining <= ticket.sla_hours * 1800 else "light border"
    return format_html(
        '<span class="badge text-bg-{}">Due in {}</span>', css, _human_duration(remaining)
    )


def _indian_grouping(integer_part: str) -> str:
    if len(integer_part) <= 3:
        return integer_part
    head, tail = integer_part[:-3], integer_part[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


@register.filter
def inr(value):
    """Format a number as Indian rupees, e.g. ₹1,25,000.00."""
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return value
    sign = "-" if amount < 0 else ""
    integer_part, _, fraction = f"{abs(amount):.2f}".partition(".")
    return f"{sign}₹{_indian_grouping(integer_part)}.{fraction}"


@register.filter
def has_feature(user, code):
    return bool(user and user.is_authenticated and user.has_feature(code))


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def percent(part, whole):
    try:
        return round(100 * float(part) / float(whole)) if whole else 0
    except (TypeError, ValueError):
        return 0


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    """Rebuild the current query string with some parameters replaced (for pagination)."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
