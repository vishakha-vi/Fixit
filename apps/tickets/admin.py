from django.contrib import admin

from .models import Reminder, Ticket, TicketEvent


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    readonly_fields = ("kind", "actor", "from_status", "to_status", "message", "created_at")
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "status", "priority_band", "category", "location", "created_by",
        "assigned_to", "created_at",
    )
    list_filter = ("status", "priority_band", "category", "location__building")
    search_fields = ("title", "description", "location__name", "location__building__name")
    raw_id_fields = ("created_by", "assigned_to", "merged_into")
    inlines = [TicketEventInline]


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "message", "ticket", "due_at", "is_done")
    list_filter = ("kind", "is_done")
    search_fields = ("message", "recipient__email")
    raw_id_fields = ("recipient", "created_by", "ticket")
