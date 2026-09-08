"""Markaz va filial admin sozlamalari."""

from django.contrib import admin

from apps.centers.models import Branch, Center
from apps.common.admin import AuditedAdminMixin


@admin.register(Center)
class CenterAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_fields = ["name", "slug", "status"]

    list_display = ["name", "slug", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Markaz", {"fields": ("name", "slug", "status")}),
        ("Texnik", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Branch)
class BranchAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_fields = ["name", "address", "phone", "status"]

    list_display = ["name", "center", "phone", "status", "created_at"]
    list_filter = ["center", "status"]
    search_fields = ["name", "address", "phone"]
    autocomplete_fields = ["center"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Filial", {"fields": ("center", "name", "address", "phone", "status")}),
        ("Texnik", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
