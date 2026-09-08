"""Foydalanuvchi va a'zolik modellari."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class UserManager(BaseUserManager):
    """Email asosidagi foydalanuvchi menejeri."""

    use_in_migrations = True

    def create_user(self, email, phone, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError("Email majburiy.")
        if not phone:
            raise ValueError("Telefon raqam majburiy.")
        extra_fields.setdefault("is_active", True)
        user = self.model(
            email=self.normalize_email(email),
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser uchun is_staff=True bo'lishi shart.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser uchun is_superuser=True bo'lishi shart.")
        return self.create_user(email, phone, first_name, last_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Tizim foydalanuvchisi.

    Diqqat: bu tenant modeli EMAS - bitta odam bir nechta markazda ishlashi mumkin,
    shuning uchun unda center FK yo'q.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    email = models.EmailField(unique=True, verbose_name="email")
    phone = models.CharField(max_length=20, unique=True, verbose_name="telefon")
    first_name = models.CharField(max_length=100, verbose_name="ismi")
    last_name = models.CharField(max_length=100, verbose_name="familiyasi")
    is_active = models.BooleanField(default=True, verbose_name="faol")
    is_staff = models.BooleanField(default=False, verbose_name="xodim (admin panelga kiradi)")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="ro'yxatdan o'tgan vaqti")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone", "first_name", "last_name"]

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name


class Membership(UUIDTimeStampedModel):
    """Foydalanuvchining muayyan markazdagi roli."""

    class Role(models.TextChoices):
        OWNER = "OWNER", "Egasi"
        ADMIN = "ADMIN", "Administrator"
        TEACHER = "TEACHER", "O'qituvchi"
        ACCOUNTANT = "ACCOUNTANT", "Hisobchi"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        INACTIVE = "INACTIVE", "Faol emas"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="memberships",
        verbose_name="foydalanuvchi",
    )
    center = models.ForeignKey(
        "centers.Center",
        on_delete=models.PROTECT,
        related_name="memberships",
        verbose_name="markaz",
    )
    branches = models.ManyToManyField(
        "centers.Branch",
        blank=True,
        related_name="memberships",
        verbose_name="filiallar",
        help_text="Bo'sh qoldirilsa - barcha filiallar.",
    )
    role = models.CharField(max_length=20, choices=Role.choices, verbose_name="roli")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="holati",
    )
    started_at = models.DateField(verbose_name="boshlangan sana")

    class Meta:
        verbose_name = "Xodim (a'zolik)"
        verbose_name_plural = "Xodimlar (a'zoliklar)"
        ordering = ["-created_at"]
        unique_together = ("user", "center", "role")

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.center.name} ({self.get_role_display()})"

    def clean(self):
        """branches ichidagi har bir filial shu markazga tegishli bo'lishi shart."""
        super().clean()
        if not self.pk:
            # M2M hali saqlanmagan - tekshiradigan narsa yo'q
            return
        begona = [
            branch.name
            for branch in self.branches.all()
            if branch.center_id != self.center_id
        ]
        if begona:
            raise ValidationError(
                {
                    "branches": (
                        "Bu filiallar tanlangan markazga tegishli emas: "
                        + ", ".join(begona)
                    )
                }
            )
