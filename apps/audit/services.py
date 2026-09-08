"""Audit yozish xizmati.

Django signal ATAYIN ishlatilmaydi: signal ichida "kim o'zgartirdi" ma'lum
bo'lmaydi va kod ko'rinmas bo'lib qoladi. Bu funksiya view/serializer ichidan
ochiq chaqiriladi.
"""

from apps.audit.models import AuditLog


def log_action(center, user, action, instance, old_values=None, new_values=None, ip_address=None):
    """
    Audit jurnaliga bitta yozuv qo'shadi.

    old_values / new_values - faqat o'zgargan maydonlar bo'lishi kerak.
    """
    return AuditLog.objects.create(
        center=center,
        user=user if (user is not None and user.is_authenticated) else None,
        action=action,
        object_type=instance._meta.label,
        object_id=str(instance.pk),
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )
