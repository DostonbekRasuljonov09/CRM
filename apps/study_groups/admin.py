"""Guruh admin sozlamalari."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from apps.study_groups.models import Group, GroupSchedule, GroupStudent
from apps.study_groups.services import apply_schedule_change


class GroupScheduleInline(admin.TabularInline):
    model = GroupSchedule
    extra = 1
    fields = ["weekday", "start_time", "end_time", "room"]
    autocomplete_fields = ["room"]
    verbose_name = "Jadval"
    verbose_name_plural = "Jadval"


class GroupStudentInline(admin.TabularInline):
    model = GroupStudent
    extra = 0
    fields = ["student", "joined_at", "left_at", "status"]
    autocomplete_fields = ["student"]
    verbose_name = "Guruhdagi o'quvchi"
    verbose_name_plural = "Guruhdagi o'quvchilar"


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "course", "branch", "teacher", "start_date", "end_date", "status"]
    list_filter = ["center", "branch", "status", "course"]
    search_fields = ["name", "course__name"]
    autocomplete_fields = ["center", "course", "branch", "teacher"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [GroupScheduleInline, GroupStudentInline]

    def save_related(self, request, form, formsets, change):
        """Jadval o'zgargach faol guruhning darslarini qayta yaratadi."""
        super().save_related(request, form, formsets, change)
        group = form.instance
        try:
            apply_schedule_change(group)
        except ValidationError as exc:
            self.message_user(
                request,
                "Darslar qayta yaratilmadi: " + "; ".join(exc.messages),
                level=messages.ERROR,
            )


@admin.register(GroupSchedule)
class GroupScheduleAdmin(admin.ModelAdmin):
    list_display = ["group", "weekday", "start_time", "end_time", "room"]
    list_filter = ["center", "weekday", "room__branch"]
    search_fields = ["group__name"]
    autocomplete_fields = ["center", "group", "room"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(GroupStudent)
class GroupStudentAdmin(admin.ModelAdmin):
    list_display = ["student", "group", "joined_at", "left_at", "status"]
    list_filter = ["center", "status", "group__branch"]
    search_fields = ["student__first_name", "student__last_name", "group__name"]
    autocomplete_fields = ["center", "group", "student"]
    readonly_fields = ["id", "created_at", "updated_at"]
