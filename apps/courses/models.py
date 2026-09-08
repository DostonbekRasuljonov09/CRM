"""Kurs, xona va bayram modellari."""

from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TenantModel


class Course(TenantModel):
    """O'quv kursi (dastur)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        ARCHIVED = "ARCHIVED", "Arxivlangan"

    name = models.CharField(max_length=200, verbose_name="nomi")
    duration_months = models.PositiveSmallIntegerField(verbose_name="davomiyligi (oy)")
    lessons_per_week = models.PositiveSmallIntegerField(verbose_name="haftasiga darslar soni")
    default_price = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="asosiy narxi (oyiga)"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="holati"
    )

    class Meta:
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"
        ordering = ["name"]
        unique_together = ("center", "name")

    def __str__(self):
        return self.name


class Room(TenantModel):
    """Filialdagi o'quv xonasi."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        CLOSED = "CLOSED", "Yopilgan"

    branch = models.ForeignKey(
        "centers.Branch",
        on_delete=models.PROTECT,
        related_name="rooms",
        verbose_name="filial",
    )
    name = models.CharField(max_length=100, verbose_name="nomi")
    capacity = models.PositiveSmallIntegerField(verbose_name="sig'imi")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="holati"
    )

    class Meta:
        verbose_name = "Xona"
        verbose_name_plural = "Xonalar"
        ordering = ["branch__name", "name"]
        unique_together = ("branch", "name")

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    def clean(self):
        super().clean()
        if self.branch_id and self.center_id and self.branch.center_id != self.center_id:
            raise ValidationError({"branch": "Filial boshqa markazga tegishli."})


class Holiday(TenantModel):
    """Dam olish / bayram kuni - bu kunga dars yaratilmaydi."""

    date = models.DateField(verbose_name="sana")
    name = models.CharField(max_length=200, verbose_name="nomi")

    class Meta:
        verbose_name = "Bayram kuni"
        verbose_name_plural = "Bayram kunlari"
        ordering = ["date"]
        unique_together = ("center", "date")

    def __str__(self):
        return f"{self.date} - {self.name}"
