"""Tenant (markaz) ajratish mantiqi."""

import uuid

from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import MultipleCentersError

CENTER_HEADER = "X-Center-Id"

# Kuchdan kuchsizga: bir markazda bir nechta rol bo'lsa eng kuchlisi olinadi
ROLE_RANK = {"OWNER": 0, "ADMIN": 1, "ACCOUNTANT": 2, "TEACHER": 3}


def active_memberships(user):
    """Foydalanuvchining faol markazlardagi barcha ACTIVE a'zoliklari."""
    from apps.accounts.models import Membership
    from apps.centers.models import Center

    return (
        Membership.objects.filter(
            user=user,
            status=Membership.Status.ACTIVE,
            center__status=Center.Status.ACTIVE,
        )
        .select_related("center")
        .order_by("center__name")
    )


def pick_membership(memberships, center):
    """Shu markazdagi eng kuchli rolli a'zolikni qaytaradi."""
    shu_markaz = [m for m in memberships if m.center_id == center.id]
    return min(shu_markaz, key=lambda m: ROLE_RANK.get(m.role, 99))


def resolve_center(request):
    """
    So'rov uchun markazni va foydalanuvchining shu markazdagi a'zoligini aniqlaydi.

    1. X-Center-Id bor -> shu markazda ACTIVE a'zolik bo'lishi shart, aks holda 403
    2. Sarlavha yo'q, bitta markazda a'zolik bor -> o'sha markaz
    3. Sarlavha yo'q, bir nechta MARKAZDA a'zolik -> 400 + markazlar ro'yxati
    4. ACTIVE a'zolik umuman yo'q -> 403

    Bitta markazda bir nechta rol (masalan ADMIN + TEACHER) "bir nechta markaz"
    hisoblanmaydi - markazlar takrorlanmaydigan qilib sanaladi.
    SUSPENDED markaz a'zolik bermaydi.

    Natija: (center, membership)
    """
    memberships = list(active_memberships(request.user))
    header = request.headers.get(CENTER_HEADER)

    if header:
        try:
            center_id = uuid.UUID(str(header).strip())
        except (ValueError, AttributeError, TypeError):
            raise PermissionDenied("X-Center-Id noto'g'ri formatda.")
        for membership in memberships:
            if membership.center_id == center_id:
                return membership.center, pick_membership(memberships, membership.center)
        raise PermissionDenied("Siz bu markazda faol emassiz yoki markaz faoliyati to'xtatilgan.")

    if not memberships:
        raise PermissionDenied("Sizda faol a'zolik yo'q.")

    # Markazlarni takrorlanmaydigan qilib yig'amiz
    markazlar = {}
    for membership in memberships:
        markazlar.setdefault(membership.center_id, membership.center)

    if len(markazlar) == 1:
        center = next(iter(markazlar.values()))
        return center, pick_membership(memberships, center)

    raise MultipleCentersError(markazlar.values())
