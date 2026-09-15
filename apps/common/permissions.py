"""Ruxsat sinflari."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

# Yozish amallari uchun standart rollar
DEFAULT_WRITE_ROLES = ("OWNER", "ADMIN")


class IsCenterMember(BasePermission):
    """Foydalanuvchining request.center bo'yicha ACTIVE a'zoligi borligini tekshiradi."""

    message = "Siz bu markazda faol emassiz."

    def has_permission(self, request, view):
        return getattr(request, "membership", None) is not None


class HasCenterRole(BasePermission):
    """
    Rol darajasidagi huquq.

    Viewset da sozlanadi:
      - `write_roles`  - yozish (POST/PATCH) uchun ruxsat etilgan rollar
                         (standart: OWNER, ADMIN)
      - `read_roles`   - o'qish uchun rollar (None = har qanday faol a'zo)
      - `action_roles` - alohida @action lar uchun {"action_nomi": (rollar,)}
      - `teacher_field` - TEACHER faqat o'ziga tegishli obyektni o'zgartira oladi
                          (masalan Lesson uchun "teacher")
    """

    message = "Bu amal uchun sizning rolingiz yetarli emas."

    def _allowed_roles(self, request, view):
        action_roles = getattr(view, "action_roles", None) or {}
        action = getattr(view, "action", None)
        if action in action_roles:
            return action_roles[action]
        if request.method in SAFE_METHODS:
            return getattr(view, "read_roles", None)
        return getattr(view, "write_roles", DEFAULT_WRITE_ROLES)

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        roles = self._allowed_roles(request, view)
        return roles is None or membership.role in roles

    def has_object_permission(self, request, view, obj):
        """O'qituvchi faqat o'zi dars beradigan obyektni o'zgartiradi."""
        if request.method in SAFE_METHODS:
            return True
        membership = getattr(request, "membership", None)
        if membership is None or membership.role != "TEACHER":
            return True
        teacher_field = getattr(view, "teacher_field", None)
        if not teacher_field:
            return True
        self.message = "Siz faqat o'zingiz dars beradigan guruh bilan ishlashingiz mumkin."
        return getattr(obj, f"{teacher_field}_id", None) == membership.id
