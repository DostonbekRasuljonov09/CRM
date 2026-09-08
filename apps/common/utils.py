"""Kichik yordamchi funksiyalar."""


def model_snapshot(instance, fields):
    """Obyektning berilgan maydonlarini oddiy dict ko'rinishida qaytaradi."""
    snapshot = {}
    for field in fields:
        value = getattr(instance, field, None)
        # JSONField ga yozish uchun sana/UUID kabi qiymatlar matnga aylantiriladi
        if value is None or isinstance(value, (str, int, float, bool)):
            snapshot[field] = value
        else:
            snapshot[field] = str(value)
    return snapshot


def diff_values(before, after):
    """
    Faqat o'zgargan maydonlarni qaytaradi.

    Natija: (old_values, new_values). Hech narsa o'zgarmasa - (None, None).
    """
    old_values = {}
    new_values = {}
    for field, new_value in after.items():
        old_value = before.get(field)
        if old_value != new_value:
            old_values[field] = old_value
            new_values[field] = new_value
    if not new_values:
        return None, None
    return old_values, new_values


def client_ip(request):
    """So'rov kelgan IP manzil."""
    return request.META.get("REMOTE_ADDR") or None


def add_months(value, months):
    """
    Sanaga oy qo'shadi (kutubxonasiz).

    Oy oxiri qisqartiriladi: 31-yanvar + 1 oy = 28/29-fevral.
    """
    import calendar

    month_index = value.month - 1 + int(months)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
