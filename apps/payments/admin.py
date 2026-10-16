from django.contrib import admin

from .models import WorkerPayment


@admin.register(WorkerPayment)
class WorkerPaymentAdmin(admin.ModelAdmin):
    list_display = ("worker_name", "kind", "amount", "status", "method", "ticket", "created_at")
    list_filter = ("status", "kind", "method")
    search_fields = ("worker_name", "description", "reference")
    raw_id_fields = ("worker", "ticket", "created_by")
