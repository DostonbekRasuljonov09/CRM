"""Davomat va dars ko'chirish testlari (13-16, 18, 19)."""

from datetime import timedelta

from django.utils import timezone

from apps.audit.models import AuditLog
from apps.common.sample_data import (
    TenantApiTestCase,
    make_enrollment,
    make_group,
    make_student,
    make_teacher,
)
from apps.lessons.models import Attendance, Lesson


class AttendanceBaseTest(TenantApiTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.group = make_group(
            self.center,
            self.course,
            self.branch,
            self.teacher,
            name="ENG-01",
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=30),
        )
        self.student = make_student(self.center, "Ali", "Valiyev")
        make_enrollment(self.group, self.student, joined_at=self.today - timedelta(days=20))

        self.lesson_past = self.make_lesson(self.today - timedelta(days=7))
        self.lesson_today = self.make_lesson(self.today)
        self.lesson_future = self.make_lesson(self.today + timedelta(days=1))

    def make_lesson(self, on_date, start="09:00", end="10:30", **extra):
        return Lesson.objects.create(
            center=self.center,
            group=self.group,
            date=on_date,
            start_time=start,
            end_time=end,
            room=self.room,
            teacher=self.teacher,
            **extra,
        )

    def mark(self, lesson, status="PRESENT", note="", student=None):
        talaba = student or self.student
        return self.api(
            "post",
            f"/api/lessons/{lesson.id}/attendance/",
            {"items": [{"student": str(talaba.id), "status": status, "note": note}]},
        )


class AttendanceTest(AttendanceBaseTest):
    def test_13_future_lesson_cannot_be_marked(self):
        """13-test: kelasi kunning darsiga davomat qo'yib bo'lmaydi."""
        response = self.mark(self.lesson_future)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("Kelajakdagi", str(response.json()))
        self.assertEqual(Attendance.objects.count(), 0)

    def test_14_marking_moves_lesson_to_held(self):
        """14-test: davomat qo'yilganda dars PLANNED -> HELD."""
        response = self.mark(self.lesson_today)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["lesson_status"], Lesson.Status.HELD)

        self.lesson_today.refresh_from_db()
        self.assertEqual(self.lesson_today.status, Lesson.Status.HELD)
        self.assertEqual(Attendance.objects.filter(lesson=self.lesson_today).count(), 1)

    def test_14b_same_day_first_marking_writes_no_audit(self):
        """Dars kunining o'zida birinchi marta belgilashda audit yozilmaydi."""
        oldingi = AuditLog.objects.count()
        self.mark(self.lesson_today)
        self.assertEqual(AuditLog.objects.count(), oldingi)

    def test_15_editing_past_attendance_writes_audit(self):
        """15-test: o'tgan darsning davomati tahrirlanganda AuditLog yoziladi."""
        birinchi = self.mark(self.lesson_past, status="ABSENT")
        self.assertEqual(birinchi.status_code, 201, birinchi.content)

        # Orqaga qaytib belgilash ham yoziladi
        self.assertTrue(
            AuditLog.objects.filter(
                object_type="lessons.Attendance", action=AuditLog.Action.CREATE
            ).exists()
        )

        ikkinchi = self.mark(self.lesson_past, status="PRESENT", note="Tuzatildi")
        self.assertEqual(ikkinchi.status_code, 201, ikkinchi.content)

        log = AuditLog.objects.get(
            object_type="lessons.Attendance", action=AuditLog.Action.UPDATE
        )
        self.assertEqual(log.old_values["status"], "ABSENT")
        self.assertEqual(log.new_values["status"], "PRESENT")
        self.assertEqual(log.center_id, self.center.id)
        self.assertEqual(log.user_id, self.admin_user.id)

    def test_16_student_joined_later_is_rejected(self):
        """16-test: o'sha sanada guruhda bo'lmagan o'quvchiga davomat qo'yilmaydi."""
        kech = make_student(self.center, "Kech", "Qo'shilgan")
        make_enrollment(self.group, kech, joined_at=self.today)

        response = self.mark(self.lesson_past, student=kech)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Attendance.objects.filter(lesson=self.lesson_past).count(), 0)

    def test_16b_student_from_another_group_is_rejected(self):
        begona = make_student(self.center, "Boshqa", "Guruhdan")
        response = self.mark(self.lesson_today, student=begona)
        self.assertEqual(response.status_code, 400, response.content)

    def test_16c_student_who_left_before_lesson_is_rejected(self):
        chiqqan = make_student(self.center, "Chiqib", "Ketgan")
        make_enrollment(
            self.group,
            chiqqan,
            joined_at=self.today - timedelta(days=20),
            left_at=self.today - timedelta(days=10),
            status="LEFT",
        )
        response = self.mark(self.lesson_past, student=chiqqan)
        self.assertEqual(response.status_code, 400, response.content)


class MoveLessonTest(AttendanceBaseTest):
    def move(self, lesson, on_date, start="14:00", end="15:30"):
        return self.api(
            "post",
            f"/api/lessons/{lesson.id}/move/",
            {
                "date": str(on_date),
                "start_time": start,
                "end_time": end,
                "room": str(self.room.id),
            },
        )

    def test_18_move_marks_old_as_moved(self):
        """18-test: dars ko'chirilganda eskisi MOVED bo'ladi va moved_to to'ladi."""
        yangi_sana = self.today + timedelta(days=3)
        response = self.move(self.lesson_future, yangi_sana)
        self.assertEqual(response.status_code, 201, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.status, Lesson.Status.MOVED)
        self.assertIsNotNone(self.lesson_future.moved_to_id)

        yangi = self.lesson_future.moved_to
        self.assertEqual(yangi.date, yangi_sana)
        self.assertEqual(yangi.status, Lesson.Status.PLANNED)
        self.assertEqual(yangi.group_id, self.group.id)
        self.assertEqual(yangi.teacher_id, self.lesson_future.teacher_id)

        # Tarix auditda saqlanadi
        self.assertTrue(
            AuditLog.objects.filter(
                object_type="lessons.Lesson", object_id=str(self.lesson_future.id)
            ).exists()
        )

    def test_19_held_lesson_cannot_be_moved(self):
        """19-test: HELD darsni ko'chirib bo'lmaydi."""
        self.lesson_today.status = Lesson.Status.HELD
        self.lesson_today.save(update_fields=["status"])

        response = self.move(self.lesson_today, self.today + timedelta(days=5))
        self.assertEqual(response.status_code, 400, response.content)

        self.lesson_today.refresh_from_db()
        self.assertEqual(self.lesson_today.status, Lesson.Status.HELD)
        self.assertIsNone(self.lesson_today.moved_to_id)

    def test_19b_move_into_conflict_is_rolled_back(self):
        """Boshqa guruh band qilgan xonaga ko'chirilsa hech narsa o'zgarmaydi."""
        teacher2 = make_teacher(self.center, "teacher2@a.uz", "+998900000012")
        group2 = make_group(
            self.center,
            self.course,
            self.branch,
            teacher2,
            name="ENG-02",
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=30),
        )
        band = Lesson.objects.create(
            center=self.center,
            group=group2,
            date=self.today + timedelta(days=3),
            start_time="14:00",
            end_time="15:30",
            room=self.room,
            teacher=teacher2,
        )

        response = self.move(self.lesson_future, band.date)
        self.assertEqual(response.status_code, 400, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.status, Lesson.Status.PLANNED)
        self.assertIsNone(self.lesson_future.moved_to_id)

    def test_19c_lesson_patch_allows_only_topic_and_cancel(self):
        """PATCH orqali faqat topic va CANCELLED."""
        mavzu = self.api(
            "patch", f"/api/lessons/{self.lesson_future.id}/", {"topic": "Present Perfect"}
        )
        self.assertEqual(mavzu.status_code, 200, mavzu.content)
        self.assertEqual(mavzu.json()["topic"], "Present Perfect")

        bekor = self.api(
            "patch", f"/api/lessons/{self.lesson_future.id}/", {"status": "CANCELLED"}
        )
        self.assertEqual(bekor.status_code, 200, bekor.content)

        held = self.api("patch", f"/api/lessons/{self.lesson_future.id}/", {"status": "HELD"})
        self.assertEqual(held.status_code, 400, held.content)

        # Sana o'zgarmaydi - read_only
        sana = self.api(
            "patch",
            f"/api/lessons/{self.lesson_future.id}/",
            {"date": str(self.today + timedelta(days=20))},
        )
        self.assertEqual(sana.status_code, 200, sana.content)
        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.date, self.today + timedelta(days=1))

    def test_19d_move_onto_own_slot_returns_400(self):
        """Bir guruhning ikki darsi bitta sana+vaqtda bo'lolmaydi."""
        band = self.make_lesson(self.today + timedelta(days=3), start="14:00", end="15:30")

        response = self.move(self.lesson_future, band.date)
        self.assertEqual(response.status_code, 400, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.status, Lesson.Status.PLANNED)
