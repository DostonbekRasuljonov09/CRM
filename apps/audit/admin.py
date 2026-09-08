"""Audit jurnali admin - faqat o'qish uchun."""

from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "center", "user", "action", "object_type", "object_id"]
    list_filter = ["center", "action", "object_type"]
    search_fields = ["object_id", "object_type"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "id",
        "center",
        "user",
        "created_at",
        "action",
        "object_type",
        "object_id",
        "old_values",
        "new_values",
        "ip_address",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
