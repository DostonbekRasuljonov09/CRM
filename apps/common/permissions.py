"""Ruxsat sinflari."""

from rest_framework.permissions import BasePermission

from apps.common.tenant import active_memberships


class IsCenterMember(BasePermission):
    """Foydalanuvchining request.center bo'yicha ACTIVE a'zoligi borligini tekshiradi."""

    message = "Siz bu markazda faol emassiz."

    def has_permission(self, request, view):
        center = getattr(request, "center", None)
        if center is None:
            return False
        return active_memberships(request.user).filter(center=center).exists()
