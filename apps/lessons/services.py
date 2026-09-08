"""Dars biznes mantig'i. Signal ishlatilmaydi - funksiyalar ochiq chaqiriladi."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.common.utils import diff_values, model_snapshot
from apps.courses.models import Holiday
from apps.lessons.models import Attendance, Lesson
from apps.study_groups.models import Group, GroupStudent

# Ziddiyatda hisobga olinadigan holatlar (CANCELLED va MOVED hisobga olinmaydi)
BLOCKING_STATUSES = (Lesson.Status.PLANNED, Lesson.Status.HELD)

ATTENDANCE_AUDIT_FIELDS = ["status", "note"]


def _overlaps(one, two):
    """Ikki dars vaqti kesishadimi."""
    return one.start_time < two.end_time and one.end_time > two.start_time


def conflict_message(lesson, other):
    """Ziddiyat haqida aniq xabar: qaysi guruh, qaysi sana, qaysi vaqt."""
    sabab = []
    if other.room_id == lesson.room_id:
        sabab.append(f"xona: {other.room.name}")
    if other.teacher_id == lesson.teacher_id:
        sabab.append(f"o'qituvchi: {other.teacher.user.get_full_name()}")
    return (
        f"{lesson.date} kuni {lesson.start_time:%H:%M}-{lesson.end_time:%H:%M} vaqti "
        f"'{other.group.name}' guruhining darsi bilan to'qnashdi "
        f"({other.start_time:%H:%M}-{other.end_time:%H:%M}, {', '.join(sabab)})."
    )


def check_conflicts(lesson, pending=()):
    """
    Dars bilan to'qnashadigan darslar ro'yxatini qaytaradi.

    Ziddiyat: shu markazda, bir xil sanada, PLANNED yoki HELD holatda,
    bir xil xona YOKI bir xil o'qituvchi bilan vaqti kesishgan dars.
    O'qituvchi ziddiyati filialdan qat'i nazar tekshiriladi.

    `pending` - hali bazaga yozilmagan darslar (bitta generatsiya ichida
    ular ham bir-biri bilan to'qnashishi mumkin).
    """
    queryset = (
        Lesson.objects.filter(
            center_id=lesson.center_id,
            date=lesson.date,
            status__in=BLOCKING_STATUSES,
            start_time__lt=lesson.end_time,
            end_time__gt=lesson.start_time,
        )
        .filter(Q(room_id=lesson.room_id) | Q(teacher_id=lesson.teacher_id))
        .select_related("group", "room", "teacher__user")
    )
    if lesson.pk:
        queryset = queryset.exclude(pk=lesson.pk)

    conflicts = list(queryset)

    for other in pending:
        if other is lesson or other.status not in BLOCKING_STATUSES:
            continue
        if other.date != lesson.date or not _overlaps(lesson, other):
            continue
        if other.room_id == lesson.room_id or other.teacher_id == lesson.teacher_id:
            conflicts.append(other)

    return conflicts


def ensure_no_conflicts(lesson, pending=()):
    """Ziddiyat topilsa ValidationError ko'taradi."""
    conflicts = check_conflicts(lesson, pending=pending)
    if conflicts:
        raise ValidationError(conflict_message(lesson, conflicts[0]))


@transaction.atomic
def generate_lessons(group, today=None):
    """
    Guruh jadvali asosida kelajakdagi darslarni qayta yaratadi.

    Idempotent: qayta chaqirilganda natija bir xil bo'ladi.
    O'tmishga va HELD/CANCELLED/MOVED darslarga tegilmaydi.
    """
    today = today or timezone.localdate()

    if group.status != Group.Status.ACTIVE:
        raise ValidationError("Darslar faqat faol guruh uchun generatsiya qilinadi.")
    if not group.end_date:
        raise ValidationError("Guruhda tugash sanasi yo'q.")

    schedules = list(group.schedules.select_related("room"))
    if not schedules:
        raise ValidationError("Guruhda jadval yo'q.")

    boshlanish = max(group.start_date, today)

    # Faqat kelajakdagi PLANNED darslar o'chiriladi.
    # Ko'chirish natijasida paydo bo'lgan darslar saqlanadi - aks holda
    # move_lesson tarixi (moved_to) uzilib qolardi.
    o_chiriladigan = list(
        Lesson.objects.filter(
            group=group,
            status=Lesson.Status.PLANNED,
            date__gte=boshlanish,
            moved_from__isnull=True,
        ).values_list("pk", flat=True)
    )
    Lesson.objects.filter(pk__in=o_chiriladigan).delete()

    # O'chirilmagan darslar (HELD, CANCELLED, MOVED, ko'chirilgan dars) egallagan
    # o'rinlar ustiga yangi dars yaratilmaydi.
    band = set(
        Lesson.objects.filter(group=group, date__gte=boshlanish).values_list(
            "date", "start_time"
        )
    )

    holidays = set(
        Holiday.objects.filter(center_id=group.center_id).values_list("date", flat=True)
    )

    new_lessons = []
    day = boshlanish
    while day <= group.end_date:
        if day in holidays:
            day += timedelta(days=1)
            continue
        for schedule in schedules:
            if schedule.weekday == day.weekday() and (day, schedule.start_time) not in band:
                new_lessons.append(
                    Lesson(
                        center_id=group.center_id,
                        group=group,
                        date=day,
                        start_time=schedule.start_time,
                        end_time=schedule.end_time,
                        room=schedule.room,
                        teacher=group.teacher,
                        status=Lesson.Status.PLANNED,
                    )
                )
        day += timedelta(days=1)

    # Ziddiyat topilsa butun amal bekor bo'ladi - birorta dars yaratilmaydi
    for lesson in new_lessons:
        ensure_no_conflicts(lesson, pending=new_lessons)

    Lesson.objects.bulk_create(new_lessons)
    return new_lessons


@transaction.atomic
def move_lesson(lesson, new_date, new_start, new_end, new_room, user=None, ip_address=None):
    """Darsni boshqa sana/vaqt/xonaga ko'chiradi, eskisini MOVED qiladi."""
    if lesson.status == Lesson.Status.HELD:
        raise ValidationError("O'tkazilgan darsni ko'chirib bo'lmaydi.")
    if lesson.status == Lesson.Status.MOVED:
        raise ValidationError("Bu dars allaqachon ko'chirilgan.")

    eski = {
        "date": str(lesson.date),
        "start_time": str(lesson.start_time),
        "status": lesson.status,
    }

    # Avval eskisi MOVED bo'ladi - shunda u ziddiyat sifatida hisoblanmaydi
    lesson.status = Lesson.Status.MOVED
    lesson.save(update_fields=["status", "updated_at"])

    new_lesson = Lesson(
        center_id=lesson.center_id,
        group=lesson.group,
        date=new_date,
        start_time=new_start,
        end_time=new_end,
        room=new_room,
        teacher=lesson.teacher,
        status=Lesson.Status.PLANNED,
        topic=lesson.topic,
    )
    # unique_together (group, date, start_time) buzilsa 500 emas, 400 qaytsin
    new_lesson.full_clean()
    new_lesson.save()

    lesson.moved_to = new_lesson
    lesson.save(update_fields=["moved_to", "updated_at"])

    ensure_no_conflicts(new_lesson)

    log_action(
        center=lesson.center,
        user=user,
        action=AuditLog.Action.UPDATE,
        instance=lesson,
        old_values=eski,
        new_values={
            "date": str(new_date),
            "start_time": str(new_start),
            "status": Lesson.Status.MOVED,
            "moved_to": str(new_lesson.pk),
        },
        ip_address=ip_address,
    )
    return new_lesson


def allowed_students(lesson):
    """Shu dars sanasida guruh ro'yxatida bo'lgan yozilishlar."""
    return GroupStudent.objects.filter(
        group_id=lesson.group_id, joined_at__lte=lesson.date
    ).filter(Q(left_at__isnull=True) | Q(left_at__gte=lesson.date))


@transaction.atomic
def mark_attendance(lesson, items, membership, ip_address=None):
    """
    Butun guruh davomatini bitta amalda belgilaydi.

    items: [{"student": <Student>, "status": "PRESENT", "note": ""}, ...]
    """
    today = timezone.localdate()

    if lesson.date > today:
        raise ValidationError("Kelajakdagi darsga davomat qo'yilmaydi.")
    if lesson.status in (Lesson.Status.CANCELLED, Lesson.Status.MOVED):
        raise ValidationError("Bekor qilingan yoki ko'chirilgan darsga davomat qo'yilmaydi.")

    ruxsat = set(allowed_students(lesson).values_list("student_id", flat=True))
    mavjud = {a.student_id: a for a in Attendance.objects.filter(lesson=lesson)}

    natija = []
    for item in items:
        student = item["student"]
        if student.pk not in ruxsat:
            raise ValidationError(f"{student} bu dars sanasida guruh ro'yxatida emas.")

        oldingi = mavjud.get(student.pk)
        eski_holat = model_snapshot(oldingi, ATTENDANCE_AUDIT_FIELDS) if oldingi else None

        attendance, _ = Attendance.objects.update_or_create(
            lesson=lesson,
            student=student,
            defaults={
                "center_id": lesson.center_id,
                "status": item["status"],
                "note": item.get("note", ""),
                "marked_by": membership,
            },
        )
        natija.append(attendance)

        yangi_holat = model_snapshot(attendance, ATTENDANCE_AUDIT_FIELDS)
        if oldingi is not None:
            # Mavjud yozuv o'zgartirildi
            old_values, new_values = diff_values(eski_holat, yangi_holat)
            if new_values:
                log_action(
                    center=lesson.center,
                    user=membership.user,
                    action=AuditLog.Action.UPDATE,
                    instance=attendance,
                    old_values=old_values,
                    new_values=new_values,
                    ip_address=ip_address,
                )
        elif lesson.date < today:
            # Orqaga qaytib belgilash. Dars kunining o'zida birinchi marta
            # belgilashda audit yozilmaydi - shovqin bo'lmasin.
            log_action(
                center=lesson.center,
                user=membership.user,
                action=AuditLog.Action.CREATE,
                instance=attendance,
                new_values=yangi_holat,
                ip_address=ip_address,
            )

    if lesson.status == Lesson.Status.PLANNED:
        lesson.status = Lesson.Status.HELD
        lesson.save(update_fields=["status", "updated_at"])

    return natija
