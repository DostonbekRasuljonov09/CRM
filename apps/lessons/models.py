"""Dars va davomat modellari - tizimning markazi."""

from django.db import models

from apps.common.models import TenantModel


class Lesson(TenantModel):
    """Bitta dars. Jadval asosida generatsiya qilinadi."""

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Rejalashtirilgan"
        HELD = "HELD", "O'tkazilgan"
        CANCELLED = "CANCELLED", "Bekor qilingan"
        MOVED = "MOVED", "Ko'chirilgan"

    group = models.ForeignKey(
        "study_groups.Group",
        on_delete=models.PROTECT,
        related_name="lessons",
        verbose_name="guruh",
    )
    date = models.DateField(verbose_name="sana")
    start_time = models.TimeField(verbose_name="boshlanish vaqti")
    end_time = models.TimeField(verbose_name="tugash vaqti")
    room = models.ForeignKey(
        "courses.Room", on_delete=models.PROTECT, related_name="lessons", verbose_name="xona"
    )
    teacher = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        related_name="lessons",
        verbose_name="o'qituvchi",
        help_text="Guruh o'qituvchisidan farq qilishi mumkin (o'rinbosar).",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED, verbose_name="holati"
    )
    topic = models.CharField(max_length=300, blank=True, verbose_name="mavzu")
    moved_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="moved_from",
        verbose_name="ko'chirilgan dars",
    )

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ["date", "start_time"]
        unique_together = ("group", "date", "start_time")
        indexes = [
            models.Index(fields=["center", "date"], name="lesson_center_date_idx"),
            models.Index(fields=["group", "date"], name="lesson_group_date_idx"),
        ]

    def __str__(self):
        return f"{self.group.name} {self.date} {self.start_time:%H:%M}"


class Attendance(TenantModel):
    """O'quvchining bitta darsdagi davomati."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Keldi"
        ABSENT = "ABSENT", "Kelmadi"
        LATE = "LATE", "Kechikdi"
        EXCUSED = "EXCUSED", "Sababli"

    lesson = models.ForeignKey(
        Lesson, on_delete=models.PROTECT, related_name="attendances", verbose_name="dars"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="attendances",
        verbose_name="o'quvchi",
    )
    status = models.CharField(max_length=20, choices=Status.choices, verbose_name="holati")
    note = models.CharField(max_length=300, blank=True, verbose_name="izoh")
    marked_by = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        related_name="marked_attendances",
        verbose_name="kim belgiladi",
    )
    marked_at = models.DateTimeField(auto_now=True, verbose_name="belgilangan vaqti")

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomat"
        ordering = ["student__last_name", "student__first_name"]
        unique_together = ("lesson", "student")

    def __str__(self):
        return f"{self.student} - {self.get_status_display()}"
