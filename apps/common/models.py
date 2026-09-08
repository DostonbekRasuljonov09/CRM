"""Barcha ilovalar uchun abstrakt bazaviy modellar."""

import uuid

from django.db import models


class UUIDTimeStampedModel(models.Model):
    """UUID kalit + yaratilgan/o'zgartirilgan vaqt."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="yaratilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="o'zgartirilgan vaqti")

    class Meta:
        abstract = True


class TenantModel(UUIDTimeStampedModel):
    """Markazga tegishli modellar uchun asos."""

    center = models.ForeignKey(
        "centers.Center",
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
        verbose_name="markaz",
    )

    class Meta:
        abstract = True
