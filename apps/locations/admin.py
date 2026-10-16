from django.contrib import admin

from apps.locations.models import Building, Location


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_critical", "created_at")
    list_filter = ("is_critical",)
    search_fields = ("name", "code")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "floor", "is_critical", "is_common_area")
    list_filter = ("building", "is_critical", "is_common_area")
    search_fields = ("name", "building__name")
