"""Ruxsat sinflari."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

# Yozish amallari uchun standart rollar
DEFAULT_WRITE_ROLES = ("OWNER", "ADMIN")

TEACHER_ROLE = "TEACHER"


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
      - `action_roles` - alohida @action lar uchun {"action_nomi": (rollar,)};
                         faqat yozish so'rovlariga qo'llanadi
      - `teacher_field` - TEACHER faqat o'ziga tegishli obyektni o'zgartira oladi
                          (masalan Lesson uchun "teacher")
    """

    message = "Bu amal uchun sizning rolingiz yetarli emas."

    def _allowed_roles(self, request, view):
        # O'qish har doim `read_roles` bo'yicha. `action_roles` faqat yozish
        # so'rovlariga qo'llanadi: aks holda ACCOUNTANT `GET .../attendance/`
        # da ham 403 olardi, holbuki davomatni ko'rish unga to'lovlar
        # bosqichida kerak bo'ladi.
        if request.method in SAFE_METHODS:
            return getattr(view, "read_roles", None)

        action_roles = getattr(view, "action_roles", None) or {}
        action = getattr(view, "action", None)
        if action in action_roles:
            return action_roles[action]
        return getattr(view, "write_roles", DEFAULT_WRITE_ROLES)

    def _memberships(self, request):
        return getattr(request, "memberships", None) or []

    def has_permission(self, request, view):
        """Rollardan birortasi yetsa ruxsat beriladi.

        Bir odam bir markazda bir nechta rolda bo'lishi mumkin (ACCOUNTANT
        va TEACHER kabi) - bu rollar bir-birining ichida emas.
        """
        memberships = self._memberships(request)
        if not memberships:
            return False
        roles = self._allowed_roles(request, view)
        if roles is None:
            return True
        return any(membership.role in roles for membership in memberships)

    def has_object_permission(self, request, view, obj):
        """O'qituvchi faqat o'zi dars beradigan obyektni o'zgartiradi.

        Cheklov faqat ruxsatni TEACHER roli berayotgan bo'lsa qo'llanadi:
        agar foydalanuvchida OWNER yoki ADMIN roli ham bo'lsa, u har qanday
        darsda ishlay oladi.
        """
        if request.method in SAFE_METHODS:
            return True
        teacher_field = getattr(view, "teacher_field", None)
        if not teacher_field:
            return True

        memberships = self._memberships(request)
        roles = self._allowed_roles(request, view)
        for membership in memberships:
            if membership.role != TEACHER_ROLE and (
                roles is None or membership.role in roles
            ):
                return True

        oz_azoliklari = {
            membership.id for membership in memberships if membership.role == TEACHER_ROLE
        }
        self.message = "Siz faqat o'zingiz dars beradigan guruh bilan ishlashingiz mumkin."
        return getattr(obj, f"{teacher_field}_id", None) in oz_azoliklari
