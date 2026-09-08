"""Guruh, guruh jadvali va guruhga yozilish modellari."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.models import Membership
from apps.common.models import TenantModel
from apps.common.utils import add_months

WEEKDAYS = [
    (0, "Dushanba"),
    (1, "Seshanba"),
    (2, "Chorshanba"),
    (3, "Payshanba"),
    (4, "Juma"),
    (5, "Shanba"),
    (6, "Yakshanba"),
]


class Group(TenantModel):
    """O'quv guruhi."""

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Rejalashtirilgan"
        ACTIVE = "ACTIVE", "Faol"
        FINISHED = "FINISHED", "Tugagan"
        CANCELLED = "CANCELLED", "Bekor qilingan"

    name = models.CharField(max_length=100, verbose_name="nomi")
    course = models.ForeignKey(
        "courses.Course", on_delete=models.PROTECT, related_name="groups", verbose_name="kurs"
    )
    branch = models.ForeignKey(
        "centers.Branch", on_delete=models.PROTECT, related_name="groups", verbose_name="filial"
    )
    teacher = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        related_name="teaching_groups",
        verbose_name="o'qituvchi",
    )
    monthly_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        verbose_name="oylik narxi",
        help_text="Bo'sh qoldirilsa kursning asosiy narxidan olinadi.",
    )
    start_date = models.DateField(verbose_name="boshlanish sanasi")
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="tugash sanasi",
        help_text="Bo'sh qoldirilsa kurs davomiyligidan hisoblanadi.",
    )
    max_students = models.PositiveSmallIntegerField(
        default=15, verbose_name="maksimal o'quvchilar soni"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED, verbose_name="holati"
    )

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ["name"]
        unique_together = ("center", "name")

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}

        # Bog'liq obyektlar shu markazga tegishlimi
        for field in ("course", "branch", "teacher"):
            obj = getattr(self, f"{field}_id", None) and getattr(self, field)
            if obj is not None and self.center_id and obj.center_id != self.center_id:
                errors[field] = "Bu obyekt boshqa markazga tegishli."

        # O'qituvchi haqiqatan o'qituvchimi
        if self.teacher_id and "teacher" not in errors:
            if self.teacher.role != Membership.Role.TEACHER:
                errors["teacher"] = "Faqat TEACHER rolidagi xodim o'qituvchi bo'la oladi."
            elif self.teacher.status != Membership.Status.ACTIVE:
                errors["teacher"] = "O'qituvchining a'zoligi faol emas."

        # Narx kursdan nusxalanadi
        if self.monthly_price is None and self.course_id and "course" not in errors:
            self.monthly_price = self.course.default_price

        # Tugash sanasi kurs davomiyligidan hisoblanadi
        if not self.end_date and self.start_date and self.course_id and "course" not in errors:
            self.end_date = add_months(self.start_date, self.course.duration_months)

        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "Tugash sanasi boshlanish sanasidan keyin bo'lishi shart."

        # ACTIVE ga o'tish shartlari
        if self.status == self.Status.ACTIVE:
            if not self.end_date:
                errors["end_date"] = "Faol guruhda tugash sanasi bo'lishi shart."
            if not self.pk or not self.schedules.exists():
                errors["status"] = "Jadvalsiz guruhni faollashtirib bo'lmaydi."

        if errors:
            raise ValidationError(errors)


class GroupSchedule(TenantModel):
    """Guruhning haftalik jadvali (Dushanba = 0)."""

    group = models.ForeignKey(
        Group, on_delete=models.PROTECT, related_name="schedules", verbose_name="guruh"
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, verbose_name="hafta kuni")
    start_time = models.TimeField(verbose_name="boshlanish vaqti")
    end_time = models.TimeField(verbose_name="tugash vaqti")
    room = models.ForeignKey(
        "courses.Room", on_delete=models.PROTECT, related_name="schedules", verbose_name="xona"
    )

    class Meta:
        verbose_name = "Guruh jadvali"
        verbose_name_plural = "Guruh jadvallari"
        ordering = ["weekday", "start_time"]
        unique_together = ("group", "weekday", "start_time")

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    def clean(self):
        super().clean()
        errors = {}
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "Tugash vaqti boshlanish vaqtidan keyin bo'lishi shart."
        if self.group_id and self.center_id and self.group.center_id != self.center_id:
            errors["group"] = "Guruh boshqa markazga tegishli."
        if self.room_id and self.group_id and self.room.branch_id != self.group.branch_id:
            errors["room"] = "Xona guruhning filialiga tegishli emas."
        if errors:
            raise ValidationError(errors)


class GroupStudent(TenantModel):
    """
    O'quvchining guruhga yozilishi.

    Oddiy M2M emas, ataylab oraliq model - qo'shilish va chiqish sanasi
    2-bosqichda to'lov hisoblash uchun kerak.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Faol"
        LEFT = "LEFT", "Chiqib ketgan"
        TRANSFERRED = "TRANSFERRED", "Boshqa guruhga o'tgan"

    group = models.ForeignKey(
        Group, on_delete=models.PROTECT, related_name="enrollments", verbose_name="guruh"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name="o'quvchi",
    )
    joined_at = models.DateField(verbose_name="qo'shilgan sana")
    left_at = models.DateField(null=True, blank=True, verbose_name="chiqqan sana")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="holati"
    )

    class Meta:
        verbose_name = "Guruhdagi o'quvchi"
        verbose_name_plural = "Guruhdagi o'quvchilar"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "student"],
                condition=Q(status="ACTIVE"),
                name="unique_active_enrollment_per_group",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.group}"

    def clean(self):
        super().clean()
        errors = {}
        if self.student_id and self.group_id and self.student.center_id != self.group.center_id:
            errors["student"] = "O'quvchi boshqa markazga tegishli."
        if self.left_at and self.joined_at and self.left_at < self.joined_at:
            errors["left_at"] = "Chiqqan sana qo'shilgan sanadan oldin bo'lishi mumkin emas."
        if errors:
            raise ValidationError(errors)
