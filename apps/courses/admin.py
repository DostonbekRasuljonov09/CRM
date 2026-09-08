"""Kurs, xona, bayram admin sozlamalari."""

from django.contrib import admin

from apps.courses.models import Course, Holiday, Room


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["name", "center", "duration_months", "lessons_per_week", "default_price", "status"]
    list_filter = ["center", "status"]
    search_fields = ["name"]
    autocomplete_fields = ["center"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "branch", "center", "capacity", "status"]
    list_filter = ["center", "branch", "status"]
    search_fields = ["name", "branch__name"]
    autocomplete_fields = ["center", "branch"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ["date", "name", "center"]
    list_filter = ["center"]
    search_fields = ["name"]
    date_hierarchy = "date"
    autocomplete_fields = ["center"]
    readonly_fields = ["id", "created_at", "updated_at"]
