"""A'zolik qoidalari. Signal ishlatilmaydi - funksiyalar ochiq chaqiriladi."""

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Membership

# Kim qaysi rollardagi a'zolikni yaratadi va tahrirlaydi.
# OWNER va ADMIN rolidagi qatorga faqat OWNER tegadi - aks holda ADMIN
# o'ziga OWNER a'zoligi yaratib yoki OWNER qatorini o'ziga o'tkazib
# markazni egallab olardi.
BOSHQARILADIGAN_ROLLAR = {
    Membership.Role.OWNER: (
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.TEACHER,
        Membership.Role.ACCOUNTANT,
    ),
    Membership.Role.ADMIN: (
        Membership.Role.TEACHER,
        Membership.Role.ACCOUNTANT,
    ),
}


def guard_role_hierarchy(actor_roles, target_role=None, yangi_role=None):
    """
    Ijrochi shu rollar bilan ishlashga haqlimi.

    `target_role` - tahrirlanayotgan a'zolikning hozirgi roli (yaratishda None)
    `yangi_role`  - yangi rol (o'zgarmasa None)

    Ikkisidan birortasi ijrochiga ruxsat etilmagan bo'lsa - 403.
    Ya'ni ADMIN OWNER qatoriga umuman tegolmaydi (hatto faqat `started_at`
    ni o'zgartirmoqchi bo'lsa ham) va rolni ADMIN yoki OWNER ga ko'tara olmaydi.
    """
    ruxsat = set()
    for rol in actor_roles:
        ruxsat.update(BOSHQARILADIGAN_ROLLAR.get(rol, ()))

    tegishli = {rol for rol in (target_role, yangi_role) if rol}
    yetmaydi = tegishli - ruxsat
    if yetmaydi:
        raise PermissionDenied(
            "Bu rollar bilan ishlash uchun huquqingiz yetarli emas: "
            + ", ".join(sorted(yetmaydi))
        )


def guard_last_owner(target, yangi_role=None, yangi_status=None):
    """
    Markazda kamida bitta faol OWNER qolishi shart.

    Diqqat: hozir API orqali bu holatga tushib bo'lmaydi - oxirgi OWNER'ning
    o'z qatorini "hech kim o'z rolini yoki holatini o'zgartira olmaydi"
    qoidasi to'sadi, boshqa rollarni esa ierarxiya to'sadi. Bu qoida
    himoyaning ikkinchi qatlami: kelajakda egalikni topshirish kabi yo'l
    qo'shilsa, markaz egasiz qolib ketmasin.
    """
    if target.role != Membership.Role.OWNER:
        return
    if target.status != Membership.Status.ACTIVE:
        return

    rolni_tushirish = yangi_role is not None and yangi_role != Membership.Role.OWNER
    faolsizlantirish = (
        yangi_status is not None and yangi_status != Membership.Status.ACTIVE
    )
    if not (rolni_tushirish or faolsizlantirish):
        return

    qolgan = (
        Membership.objects.filter(
            center_id=target.center_id,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        .exclude(pk=target.pk)
        .count()
    )
    if qolgan == 0:
        raise ValidationError(
            {"role": "Markazda kamida bitta faol OWNER qolishi shart."}
        )
