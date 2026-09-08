"""Audit jurnali. Yozuvlar o'zgarmas (immutable)."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models


class AuditLogQuerySet(models.QuerySet):
    """Guruh amallarini ham yopadi.

    Faqat model darajasidagi save()/delete() ni override qilish yetarli emas:
    QuerySet.update() va QuerySet.delete() model metodlarini umuman chaqirmaydi
    va to'g'ridan-to'g'ri SQL yuboradi. bulk_update() ham update() ustida ishlaydi.
    """

    def update(self, **kwargs):
        raise ValidationError("Audit yozuvlarini o'zgartirib bo'lmaydi.")

    def delete(self):
        raise ValidationError("Audit yozuvlarini o'chirib bo'lmaydi.")


class AuditLog(models.Model):
    """Kim, qachon, nimani o'zgartirgani."""

    class Action(models.TextChoices):
        CREATE = "CREATE", "Yaratildi"
        UPDATE = "UPDATE", "O'zgartirildi"
        DELETE = "DELETE", "O'chirildi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    center = models.ForeignKey(
        "centers.Center",
        on_delete=models.PROTECT,
        related_name="audit_logs",
        verbose_name="markaz",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="foydalanuvchi",
        help_text="Bo'sh bo'lsa - tizim amali.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="vaqti")
    action = models.CharField(max_length=10, choices=Action.choices, verbose_name="amal")
    object_type = models.CharField(max_length=100, verbose_name="obyekt turi")
    object_id = models.CharField(max_length=64, verbose_name="obyekt ID")
    old_values = models.JSONField(null=True, blank=True, verbose_name="eski qiymatlar")
    new_values = models.JSONField(null=True, blank=True, verbose_name="yangi qiymatlar")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP manzil")

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit jurnali"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["center", "created_at"], name="audit_center_created_idx"),
            models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()}: {self.object_type} ({self.created_at:%Y-%m-%d %H:%M})"

    def save(self, *args, **kwargs):
        """Faqat bir marta yoziladi - keyin o'zgartirib bo'lmaydi."""
        if not self._state.adding:
            raise ValidationError("Audit yozuvini o'zgartirib bo'lmaydi.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit yozuvini o'chirib bo'lmaydi.")
