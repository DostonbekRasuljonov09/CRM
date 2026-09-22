"""Davomat va dars ko'chirish testlari (13-16, 18, 19)."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Membership
from apps.audit.models import AuditLog
from apps.common.sample_data import (
    TenantApiTestCase,
    auth_headers,
    get_token,
    make_enrollment,
    make_group,
    make_membership,
    make_student,
    make_teacher,
    make_user,
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


class MultiRoleAttendanceTest(AttendanceBaseTest):
    """3-muammo: bir markazda bir nechta rol bo'lsa TEACHER huquqi yo'qolardi.

    `pick_membership` faqat "eng kuchli" rolni olardi va ACCOUNTANT'ni
    TEACHER'dan kuchli deb hisoblardi. Lekin bu rollar bir-birining ichida
    emas - huquqlari har xil.
    """

    def headers_for(self, email):
        return auth_headers(get_token(self.client, email), self.center)

    def post_attendance(self, lesson, headers, student=None):
        return self.client.post(
            f"/api/lessons/{lesson.id}/attendance/",
            {"items": [{"student": str((student or self.student).id), "status": "PRESENT"}]},
            content_type="application/json",
            headers=headers,
        )

    def boshqa_oqituvchi_darsi(self):
        """Boshqa o'qituvchiga biriktirilgan dars (shu o'quvchi bilan)."""
        boshqa = make_teacher(self.center, "t2@a.uz", "+998900000012")
        group = make_group(
            self.center,
            self.course,
            self.branch,
            boshqa,
            name="BOSHQA-GURUH",
            start_date=self.today - timedelta(days=20),
            end_date=self.today + timedelta(days=20),
        )
        make_enrollment(group, self.student, joined_at=self.today - timedelta(days=15))
        return Lesson.objects.create(
            center=self.center,
            group=group,
            date=self.today,
            start_time="14:00",
            end_time="15:30",
            room=self.room,
            teacher=boshqa,
        )

    def test_i3a_accountant_and_teacher_marks_own_lesson(self):
        """ACCOUNTANT + TEACHER o'z darsiga davomat qo'yadi."""
        make_membership(self.teacher.user, self.center, role=Membership.Role.ACCOUNTANT)

        response = self.post_attendance(self.lesson_today, self.headers_for("teacher@a.uz"))
        self.assertEqual(response.status_code, 201, response.content)

        # marked_by ga TEACHER a'zoligi yoziladi, ACCOUNTANT emas
        self.assertEqual(
            response.json()["attendances"][0]["marked_by"], str(self.teacher.id)
        )

    def test_i3b_accountant_and_teacher_cannot_mark_another_lesson(self):
        """Obyekt darajasidagi cheklov saqlanadi."""
        make_membership(self.teacher.user, self.center, role=Membership.Role.ACCOUNTANT)
        begona = self.boshqa_oqituvchi_darsi()

        response = self.post_attendance(begona, self.headers_for("teacher@a.uz"))
        self.assertEqual(response.status_code, 403, response.content)

    def test_i3c_admin_and_teacher_behaviour_is_unchanged(self):
        """ADMIN + TEACHER: ADMIN huquqi bilan har qanday darsga qo'yadi."""
        make_membership(self.admin_user, self.center, role=Membership.Role.TEACHER)
        begona = self.boshqa_oqituvchi_darsi()

        oz = self.post_attendance(self.lesson_today, self.headers)
        self.assertEqual(oz.status_code, 201, oz.content)

        boshqa = self.post_attendance(begona, self.headers)
        self.assertEqual(boshqa.status_code, 201, boshqa.content)

    def test_i3d_accountant_alone_cannot_mark_attendance(self):
        """Faqat ACCOUNTANT bo'lsa davomat qo'yolmaydi."""
        hisobchi_user = make_user("hisobchi@a.uz", "+998900000033")
        make_membership(hisobchi_user, self.center, role=Membership.Role.ACCOUNTANT)

        response = self.post_attendance(
            self.lesson_today, self.headers_for("hisobchi@a.uz")
        )
        self.assertEqual(response.status_code, 403, response.content)


class LessonCancelTest(AttendanceBaseTest):
    """4-muammo: TEACHER darsni bekor qilardi va audit yozilmasdi."""

    def as_teacher(self, url, data):
        return self.client.patch(
            url,
            data,
            content_type="application/json",
            headers=auth_headers(get_token(self.client, "teacher@a.uz"), self.center),
        )

    def audit_yozuvlari(self, lesson):
        return AuditLog.objects.filter(
            object_type="lessons.Lesson", object_id=str(lesson.id)
        )

    def test_i4a_teacher_cannot_cancel_lesson(self):
        response = self.as_teacher(
            f"/api/lessons/{self.lesson_future.id}/", {"status": "CANCELLED"}
        )
        self.assertEqual(response.status_code, 403, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.status, Lesson.Status.PLANNED)

    def test_i4b_teacher_can_still_write_topic(self):
        response = self.as_teacher(
            f"/api/lessons/{self.lesson_future.id}/", {"topic": "Present Perfect"}
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.topic, "Present Perfect")

    def test_i4c_teacher_cannot_send_status_with_topic(self):
        """`status` bilan birga `topic` yuborilsa ham to'siladi."""
        response = self.as_teacher(
            f"/api/lessons/{self.lesson_future.id}/",
            {"topic": "Mavzu", "status": "CANCELLED"},
        )
        self.assertEqual(response.status_code, 403, response.content)

        self.lesson_future.refresh_from_db()
        self.assertEqual(self.lesson_future.status, Lesson.Status.PLANNED)
        self.assertEqual(self.lesson_future.topic, "")

    def test_i4d_admin_cancel_is_audited(self):
        oldingi = self.audit_yozuvlari(self.lesson_future).count()

        response = self.api(
            "patch", f"/api/lessons/{self.lesson_future.id}/", {"status": "CANCELLED"}
        )
        self.assertEqual(response.status_code, 200, response.content)

        yozuvlar = self.audit_yozuvlari(self.lesson_future)
        self.assertEqual(yozuvlar.count(), oldingi + 1)

        log = yozuvlar.get(action=AuditLog.Action.UPDATE)
        self.assertEqual(log.old_values, {"status": "PLANNED"})
        self.assertEqual(log.new_values, {"status": "CANCELLED"})
        self.assertEqual(log.center_id, self.center.id)
        self.assertEqual(log.user_id, self.admin_user.id)

    def test_i4e_topic_change_is_not_audited(self):
        """Mavzu o'zgarishi auditga yozilmaydi - shovqin bo'lmasin."""
        oldingi = self.audit_yozuvlari(self.lesson_future).count()

        response = self.api(
            "patch", f"/api/lessons/{self.lesson_future.id}/", {"topic": "Mavzu"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.audit_yozuvlari(self.lesson_future).count(), oldingi)
