"""Markaz va filial modellari."""

from django.db import models

from apps.common.models import TenantModel, UUIDTimeStampedModel


class Center(UUIDTimeStampedModel):
    """O'quv markazi (tenant). O'zida center FK yo'q."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        SUSPENDED = "SUSPENDED", "To'xtatilgan"

    name = models.CharField(max_length=200, verbose_name="nomi")
    slug = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name="qisqa nom",
        help_text="Kelajakda subdomen uchun ishlatiladi.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="holati",
    )

    class Meta:
        verbose_name = "Markaz"
        verbose_name_plural = "Markazlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(TenantModel):
    """Markazning filiali."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        CLOSED = "CLOSED", "Yopilgan"

    name = models.CharField(max_length=200, verbose_name="nomi")
    address = models.CharField(max_length=300, blank=True, verbose_name="manzili")
    phone = models.CharField(max_length=20, blank=True, verbose_name="telefon")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="holati",
    )

    class Meta:
        verbose_name = "Filial"
        verbose_name_plural = "Filiallar"
        ordering = ["name"]
        unique_together = ("center", "name")

    def __str__(self):
        return f"{self.name} ({self.center.name})"
