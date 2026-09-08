"""Tenant (markaz) ajratish mantiqi."""

import uuid

from rest_framework.exceptions import PermissionDenied

from apps.common.exceptions import MultipleCentersError

CENTER_HEADER = "X-Center-Id"


def active_memberships(user):
    """Foydalanuvchining barcha ACTIVE a'zoliklari."""
    from apps.accounts.models import Membership

    return (
        Membership.objects.filter(user=user, status=Membership.Status.ACTIVE)
        .select_related("center")
        .order_by("center__name")
    )


def resolve_center(request):
    """
    So'rov uchun markazni aniqlaydi.

    1. X-Center-Id bor -> shu markazda ACTIVE a'zolik bo'lishi shart, aks holda 403
    2. Sarlavha yo'q, bitta ACTIVE a'zolik bor -> o'sha markaz
    3. Sarlavha yo'q, bir nechta ACTIVE a'zolik -> 400 + markazlar ro'yxati
    4. ACTIVE a'zolik umuman yo'q -> 403
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
                return membership.center
        raise PermissionDenied("Siz bu markazda faol emassiz.")

    if not memberships:
        raise PermissionDenied("Sizda faol a'zolik yo'q.")

    if len(memberships) == 1:
        return memberships[0].center

    raise MultipleCentersError([m.center for m in memberships])
