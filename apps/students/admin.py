"""O'quvchi admin sozlamalari."""

from django.contrib import admin

from apps.students.models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "center", "status"]
    list_filter = ["center", "status"]
    search_fields = ["first_name", "last_name", "phone", "parent_phone"]
    autocomplete_fields = ["center"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("O'quvchi", {"fields": ("center", "first_name", "last_name", "phone", "birth_date", "status")}),
        ("Ota-ona", {"fields": ("parent_name", "parent_phone")}),
        ("Texnik", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
