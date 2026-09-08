"""Guruh biznes mantig'i. Signal ishlatilmaydi - funksiyalar ochiq chaqiriladi."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.lessons.services import generate_lessons
from apps.study_groups.models import Group, GroupStudent


@transaction.atomic
def activate_group(group):
    """
    Guruhni ACTIVE qiladi va darslarni generatsiya qiladi.

    Jadvalsiz yoki tugash sanasisiz guruh faollashmaydi - buni
    Group.clean() tekshiradi.
    """
    group.status = Group.Status.ACTIVE
    group.full_clean()
    group.save()
    return generate_lessons(group)


def apply_schedule_change(group):
    """Jadval o'zgargach faol guruh darslarini qayta yaratadi."""
    if group.status == Group.Status.ACTIVE:
        return generate_lessons(group)
    return []


def sync_teacher(group, today=None):
    """
    O'qituvchi almashganda faqat kelajakdagi PLANNED darslarni yangilaydi.

    HELD, CANCELLED, MOVED va o'tgan darslarga tegilmaydi - 3-bosqichda
    maosh o'sha yozuvlardan hisoblanadi.
    """
    today = today or timezone.localdate()
    return Lesson.objects.filter(
        group=group, status=Lesson.Status.PLANNED, date__gte=today
    ).update(teacher=group.teacher)


@transaction.atomic
def add_student(group, student, joined_at=None):
    """
    Guruhga o'quvchi qo'shadi.

    Limitdan oshsa rad etilmaydi, lekin ogohlantirish qaytadi.
    Natija: (enrollment, warning)
    """
    joined_at = joined_at or timezone.localdate()

    if student.center_id != group.center_id:
        raise ValidationError({"student": "O'quvchi boshqa markazga tegishli."})

    if GroupStudent.objects.filter(
        group=group, student=student, status=GroupStudent.Status.ACTIVE
    ).exists():
        raise ValidationError({"student": "Bu o'quvchi guruhda allaqachon faol."})

    enrollment = GroupStudent(
        center_id=group.center_id,
        group=group,
        student=student,
        joined_at=joined_at,
        status=GroupStudent.Status.ACTIVE,
    )
    enrollment.full_clean()
    enrollment.save()

    faol_soni = GroupStudent.objects.filter(
        group=group, status=GroupStudent.Status.ACTIVE
    ).count()
    warning = None
    if faol_soni > group.max_students:
        warning = f"Guruh limiti oshdi: {faol_soni}/{group.max_students}"

    return enrollment, warning


@transaction.atomic
def leave_group(enrollment, left_at=None):
    """O'quvchini guruhdan chiqaradi (o'chirmaydi - status LEFT)."""
    if enrollment.status != GroupStudent.Status.ACTIVE:
        raise ValidationError("Bu yozilish allaqachon yopilgan.")

    enrollment.left_at = left_at or timezone.localdate()
    enrollment.status = GroupStudent.Status.LEFT
    enrollment.full_clean()
    enrollment.save()
    return enrollment
