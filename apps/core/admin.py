from django.contrib import admin

from .models import DemoClock


@admin.register(DemoClock)
class DemoClockAdmin(admin.ModelAdmin):
    list_display = ("id", "offset_seconds")
