"""O'quvchi modeli."""

from django.db import models

from apps.common.models import TenantModel


class Student(TenantModel):
    """
    O'quvchi.

    Diqqat: Student - User EMAS. O'quvchi tizimga kirmaydi va User bilan
    bog'lanmaydi. `phone` da unique yo'q - aka-uka bir raqamdan foydalanishi mumkin.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        ARCHIVED = "ARCHIVED", "Arxivlangan"

    first_name = models.CharField(max_length=100, verbose_name="ismi")
    last_name = models.CharField(max_length=100, verbose_name="familiyasi")
    phone = models.CharField(max_length=20, blank=True, verbose_name="telefon")
    birth_date = models.DateField(null=True, blank=True, verbose_name="tug'ilgan sana")
    parent_name = models.CharField(max_length=200, blank=True, verbose_name="ota-ona ismi")
    parent_phone = models.CharField(max_length=20, blank=True, verbose_name="ota-ona telefoni")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="holati"
    )

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
