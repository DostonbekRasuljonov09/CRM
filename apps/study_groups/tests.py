"""Guruh validatsiyasi va o'quvchi yozilish testlari (1-5, 17, 20, 21)."""

from datetime import date, timedelta

from apps.accounts.models import Membership
from apps.common.sample_data import (
    TenantApiTestCase,
    make_branch,
    make_center,
    make_course,
    make_membership,
    make_room,
    make_student,
    make_teacher,
    make_user,
)
from apps.study_groups.models import Group, GroupStudent


class GroupValidationTest(TenantApiTestCase):
    def setUp(self):
        super().setUp()
        self.payload = {
            "name": "ENG-B-04",
            "course": str(self.course.id),
            "branch": str(self.branch.id),
            "teacher": str(self.teacher.id),
            "start_date": "2026-10-01",
            "end_date": "2027-04-01",
        }

    def test_01_foreign_center_teacher_rejected(self):
        """1-test: begona markaz o'qituvchisi biriktirilmaydi."""
        center_b = make_center("B markaz", "b-markaz")
        begona = make_teacher(center_b, "b.teacher@b.uz", "+998900000099")

        response = self.api("post", "/api/groups/", {**self.payload, "teacher": str(begona.id)})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("teacher", response.json())
        self.assertFalse(Group.objects.filter(name="ENG-B-04").exists())

    def test_02_non_teacher_membership_rejected(self):
        """2-test: roli TEACHER bo'lmagan xodim o'qituvchi bo'la olmaydi."""
        user = make_user("hisobchi@a.uz", "+998900000021")
        hisobchi = make_membership(user, self.center, role=Membership.Role.ACCOUNTANT)

        response = self.api("post", "/api/groups/", {**self.payload, "teacher": str(hisobchi.id)})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("teacher", response.json())

    def test_02b_inactive_teacher_rejected(self):
        self.teacher.status = Membership.Status.INACTIVE
        self.teacher.save(update_fields=["status"])

        response = self.api("post", "/api/groups/", self.payload)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("teacher", response.json())

    def test_03_foreign_branch_or_room_rejected(self):
        """3-test: begona markazning filiali yoki xonasi biriktirilmaydi."""
        center_b = make_center("B markaz", "b-markaz")
        begona_branch = make_branch(center_b, "B filial")

        response = self.api(
            "post", "/api/groups/", {**self.payload, "branch": str(begona_branch.id)}
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("branch", response.json())

        # Endi begona xona - jadval orqali
        group = self.api("post", "/api/groups/", self.payload).json()
        begona_room = make_room(center_b, begona_branch, "B-101")
        jadval = self.api(
            "post",
            f"/api/groups/{group['id']}/schedules/",
            {"weekday": 0, "start_time": "09:00", "end_time": "10:30", "room": str(begona_room.id)},
        )
        self.assertEqual(jadval.status_code, 400, jadval.content)
        self.assertIn("room", jadval.json())

    def test_04_end_date_computed_from_course_duration(self):
        """4-test: end_date bo'sh bo'lsa kurs davomiyligidan hisoblanadi."""
        payload = dict(self.payload)
        payload.pop("end_date")
        payload["start_date"] = "2026-10-15"

        response = self.api("post", "/api/groups/", payload)
        self.assertEqual(response.status_code, 201, response.content)
        # kurs 6 oylik
        self.assertEqual(response.json()["end_date"], "2027-04-15")

    def test_04b_monthly_price_copied_from_course(self):
        response = self.api("post", "/api/groups/", self.payload)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["monthly_price"], "500000.00")

    def test_05_group_without_schedule_cannot_activate(self):
        """5-test: jadvalsiz guruhni ACTIVE qilib bo'lmaydi."""
        group = self.api("post", "/api/groups/", self.payload).json()

        response = self.api("post", f"/api/groups/{group['id']}/activate/")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("status", response.json())
        self.assertEqual(Group.objects.get(pk=group["id"]).status, Group.Status.PLANNED)

    def test_20_foreign_group_returns_404(self):
        """20-test: begona markazning guruhi so'ralganda 404."""
        center_b = make_center("B markaz", "b-markaz")
        branch_b = make_branch(center_b, "B filial")
        course_b = make_course(center_b, name="B kurs")
        teacher_b = make_teacher(center_b, "b.teacher@b.uz", "+998900000098")
        from apps.common.sample_data import make_group

        begona = make_group(
            center_b, course_b, branch_b, teacher_b, name="B-GURUH", start_date=date(2026, 10, 1)
        )

        response = self.api("get", f"/api/groups/{begona.id}/")
        self.assertEqual(response.status_code, 404, response.content)
        self.assertTrue(Group.objects.filter(pk=begona.pk).exists())


class EnrollmentTest(TenantApiTestCase):
    """17- va 21-testlar: guruhga o'quvchi qo'shish."""

    def setUp(self):
        super().setUp()
        from apps.common.sample_data import make_group

        self.group = make_group(
            self.center,
            self.course,
            self.branch,
            self.teacher,
            name="ENG-01",
            start_date=date(2026, 10, 1),
            max_students=2,
        )
        self.url = f"/api/groups/{self.group.id}/students/"

    def test_17_same_student_cannot_be_active_twice(self):
        """17-test: bir o'quvchi bitta guruhda ikki marta ACTIVE bo'lolmaydi."""
        student = make_student(self.center, "Ali", "Valiyev")

        birinchi = self.api("post", self.url, {"student": str(student.id), "joined_at": "2026-10-01"})
        self.assertEqual(birinchi.status_code, 201, birinchi.content)

        ikkinchi = self.api("post", self.url, {"student": str(student.id), "joined_at": "2026-10-05"})
        self.assertEqual(ikkinchi.status_code, 400, ikkinchi.content)
        self.assertEqual(
            GroupStudent.objects.filter(
                group=self.group, student=student, status=GroupStudent.Status.ACTIVE
            ).count(),
            1,
        )

    def test_17b_student_can_rejoin_after_leaving(self):
        """Chiqib ketgandan keyin qayta qo'shilish mumkin."""
        student = make_student(self.center, "Ali", "Valiyev")
        yozilish = self.api("post", self.url, {"student": str(student.id)}).json()

        chiqish = self.api("post", f"{self.url}{yozilish['id']}/leave/", {"left_at": "2026-11-01"})
        self.assertEqual(chiqish.status_code, 200, chiqish.content)
        self.assertEqual(chiqish.json()["status"], "LEFT")

        qayta = self.api("post", self.url, {"student": str(student.id), "joined_at": "2026-12-01"})
        self.assertEqual(qayta.status_code, 201, qayta.content)

    def test_17c_foreign_student_rejected(self):
        center_b = make_center("B markaz", "b-markaz")
        begona = make_student(center_b, "Begona", "O'quvchi")

        response = self.api("post", self.url, {"student": str(begona.id)})
        self.assertEqual(response.status_code, 400, response.content)

    def test_21_over_limit_adds_with_warning(self):
        """21-test: limitdan oshsa qo'shiladi, lekin warning qaytadi."""
        for index in range(2):
            student = make_student(self.center, f"O'quvchi{index}", "Familiya")
            javob = self.api("post", self.url, {"student": str(student.id)})
            self.assertEqual(javob.status_code, 201, javob.content)
            self.assertNotIn("warning", javob.json())

        uchinchi = make_student(self.center, "Uchinchi", "O'quvchi")
        response = self.api("post", self.url, {"student": str(uchinchi.id)})

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["warning"], "Guruh limiti oshdi: 3/2")
        self.assertEqual(
            GroupStudent.objects.filter(
                group=self.group, status=GroupStudent.Status.ACTIVE
            ).count(),
            3,
        )
