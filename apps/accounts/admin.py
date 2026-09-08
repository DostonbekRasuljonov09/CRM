"""Foydalanuvchi va a'zolik admin sozlamalari."""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from apps.accounts.models import Membership, User
from apps.common.admin import AuditedAdminMixin


class UserCreateForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "phone", "first_name", "last_name")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """username maydoni yo'q - email asosida."""

    add_form = UserCreateForm
    form = UserEditForm
    model = User

    list_display = ["email", "first_name", "last_name", "phone", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "phone", "first_name", "last_name"]
    ordering = ["email"]
    readonly_fields = ["id", "date_joined", "last_login"]
    filter_horizontal = ["groups", "user_permissions"]

    fieldsets = (
        ("Kirish", {"fields": ("email", "password")}),
        ("Shaxsiy ma'lumot", {"fields": ("first_name", "last_name", "phone")}),
        ("Huquqlar", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Texnik", {"fields": ("id", "date_joined", "last_login"), "classes": ("collapse",)}),
    )
    add_fieldsets = (
        (
            "Yangi foydalanuvchi",
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )


class MembershipAdminForm(forms.ModelForm):
    """branches faqat shu markaz filiallaridan bo'lishini tekshiradi."""

    class Meta:
        model = Membership
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        center = cleaned.get("center")
        branches = cleaned.get("branches")
        if center and branches:
            begona = [b.name for b in branches if b.center_id != center.id]
            if begona:
                self.add_error(
                    "branches",
                    "Bu filiallar tanlangan markazga tegishli emas: " + ", ".join(begona),
                )
        return cleaned


@admin.register(Membership)
class MembershipAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_fields = ["role", "status", "started_at"]

    form = MembershipAdminForm
    list_display = ["user", "center", "role", "status", "started_at"]
    list_filter = ["center", "role", "status"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "center__name"]
    autocomplete_fields = ["user", "center"]
    filter_horizontal = ["branches"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("A'zolik", {"fields": ("user", "center", "role", "status", "started_at", "branches")}),
        ("Texnik", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


# django.contrib.auth.models.Group ni admin'dan olib tashlaymiz: rollar
# Membership orqali boshqariladi va admin panelda ikkita "Guruh" chalkashtiradi.
from django.contrib.auth.models import Group as AuthGroup  # noqa: E402

if admin.site.is_registered(AuthGroup):
    admin.site.unregister(AuthGroup)
