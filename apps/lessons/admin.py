"""Dars va davomat admin sozlamalari."""

from django.contrib import admin

from apps.lessons.models import Attendance, Lesson


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    fields = ["student", "status", "note", "marked_by"]
    autocomplete_fields = ["student"]
    verbose_name = "Davomat"
    verbose_name_plural = "Davomat"


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["date", "start_time", "group", "room", "teacher", "status"]
    list_filter = ["center", "status", "group__branch", "date"]
    search_fields = ["group__name", "topic"]
    date_hierarchy = "date"
    autocomplete_fields = ["center", "group", "room", "teacher", "moved_to"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [AttendanceInline]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["lesson", "student", "status", "marked_by", "marked_at"]
    list_filter = ["center", "status"]
    search_fields = ["student__first_name", "student__last_name"]
    autocomplete_fields = ["center", "lesson", "student", "marked_by"]
    readonly_fields = ["id", "created_at", "updated_at", "marked_at"]
