"""Guruh biznes mantig'i. Signal ishlatilmaydi - funksiyalar ochiq chaqiriladi."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.lessons.services import ensure_no_conflicts, generate_lessons
from apps.study_groups.models import Group, GroupStudent


@transaction.atomic
def activate_group(group):
    """
    Guruhni ACTIVE qiladi va darslarni generatsiya qiladi.

    Jadvalsiz yoki tugash sanasisiz guruh faollashmaydi - buni
    Group.clean() tekshiradi.

    Bekor qilingan guruh qayta faollashmaydi: cancel_group kelajakdagi
    darslarni CANCELLED qilib qo'yadi, generate_lessons esa band
    o'rinlarga yangi dars yaratmaydi - natijada guruh ACTIVE bo'lib,
    lekin birorta darssiz qolardi. Bekor qilingan guruh o'rniga yangisi
    ochiladi - shunda eski darslar va davomat tarixi ham buzilmaydi.
    """
    if group.status == Group.Status.CANCELLED:
        raise ValidationError(
            {"status": "Bekor qilingan guruhni qayta faollashtirib bo'lmaydi. "
                       "Yangi guruh oching."}
        )

    group.status = Group.Status.ACTIVE
    group.full_clean()
    group.save()
    return generate_lessons(group)


def apply_schedule_change(group):
    """Jadval o'zgargach faol guruh darslarini qayta yaratadi."""
    if group.status == Group.Status.ACTIVE:
        return generate_lessons(group)
    return []


@transaction.atomic
def sync_teacher(group, today=None):
    """
    O'qituvchi almashganda faqat kelajakdagi PLANNED darslarni yangilaydi.

    HELD, CANCELLED, MOVED va o'tgan darslarga tegilmaydi - 3-bosqichda
    maosh o'sha yozuvlardan hisoblanadi.

    Yangi o'qituvchining jadvali bo'sh bo'lishi shart: aks holda bitta odam
    bir vaqtda ikki joyda dars berib qolardi. Ziddiyat topilsa butun amal
    bekor bo'ladi va o'qituvchi almashmaydi.
    """
    today = today or timezone.localdate()
    lessons = list(
        Lesson.objects.filter(
            group=group, status=Lesson.Status.PLANNED, date__gte=today
        )
    )
    if not lessons:
        return 0

    Lesson.objects.filter(pk__in=[lesson.pk for lesson in lessons]).update(
        teacher=group.teacher
    )

    for lesson in lessons:
        lesson.teacher = group.teacher
        ensure_no_conflicts(lesson)

    return len(lessons)


@transaction.atomic
def cancel_group(group, today=None):
    """
    Guruhni bekor qiladi va kelajakdagi PLANNED darslarni CANCELLED qiladi.

    Aks holda bekor qilingan guruhning darslari xona va o'qituvchini
    band qilib turardi.
    """
    today = today or timezone.localdate()
    group.status = Group.Status.CANCELLED
    group.full_clean()
    group.save()
    return Lesson.objects.filter(
        group=group, status=Lesson.Status.PLANNED, date__gte=today
    ).update(status=Lesson.Status.CANCELLED)


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
