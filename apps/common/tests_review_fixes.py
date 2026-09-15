"""Ustoz sharhida topilgan kamchiliklar uchun regressiya testlari."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Membership
from apps.centers.models import Branch
from apps.common.sample_data import (
    TenantApiTestCase,
    auth_headers,
    get_token,
    make_enrollment,
    make_group,
    make_schedule,
    make_student,
    make_teacher,
    make_user,
)
from apps.lessons.models import Lesson


class ReviewFixBase(TenantApiTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.start = self.today + timedelta(days=(7 - self.today.weekday()) % 7 or 7)
        self.end = self.start + timedelta(days=13)
        self.t_headers = auth_headers(get_token(self.client, "teacher@a.uz"), self.center)

    def as_teacher(self, method, url, data=None):
        kwargs = {"headers": self.t_headers}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(self.client, method)(url, **kwargs)

    def active_group(self, name="ENG-01", teacher=None, room=None, branch=None):
        group = make_group(
            self.center,
            self.course,
            branch or self.branch,
            teacher or self.teacher,
            name=name,
            start_date=self.start,
            end_date=self.end,
        )
        make_schedule(group, 0, room or self.room, "09:00", "10:30")
        response = self.api("post", f"/api/groups/{group.id}/activate/")
        assert response.status_code == 200, response.content
        group.refresh_from_db()
        return group


class RolePermissionTest(ReviewFixBase):
    """1-kamchilik: rol darajasidagi huquqlar yo'q edi."""

    def test_r1a_teacher_cannot_promote_self(self):
        response = self.as_teacher(
            "patch", f"/api/memberships/{self.teacher.id}/", {"role": "OWNER"}
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, Membership.Role.TEACHER)

    def test_r1b_teacher_cannot_create_membership(self):
        boshqa = make_user("yangi@a.uz", "+998900000077")
        response = self.as_teacher(
            "post",
            "/api/memberships/",
            {"user": str(boshqa.id), "role": "ADMIN", "started_at": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Membership.objects.filter(user=boshqa).exists())

    def test_r1c_teacher_cannot_see_staff_list(self):
        response = self.as_teacher("get", "/api/memberships/")
        self.assertEqual(response.status_code, 403, response.content)

    def test_r1d_teacher_cannot_create_reference_data(self):
        holatlar = (
            ("/api/branches/", {"name": "Begona filial"}),
            ("/api/rooms/", {"branch": str(self.branch.id), "name": "X", "capacity": 5}),
            ("/api/students/", {"first_name": "A", "last_name": "B"}),
        )
        for url, data in holatlar:
            response = self.as_teacher("post", url, data)
            self.assertEqual(response.status_code, 403, f"{url}: {response.content}")
        self.assertFalse(Branch.objects.filter(name="Begona filial").exists())

    def test_r1e_teacher_can_read_but_not_write_groups(self):
        group = self.active_group()
        self.assertEqual(self.as_teacher("get", "/api/groups/").status_code, 200)
        self.assertEqual(self.as_teacher("get", "/api/lessons/").status_code, 200)

        yozish = self.as_teacher("patch", f"/api/groups/{group.id}/", {"name": "YANGI"})
        self.assertEqual(yozish.status_code, 403, yozish.content)

    def test_r1f_admin_can_manage_memberships(self):
        boshqa = make_user("yangi@a.uz", "+998900000077")
        response = self.api(
            "post",
            "/api/memberships/",
            {"user": str(boshqa.id), "role": "TEACHER", "started_at": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_r1g_nobody_can_change_own_role(self):
        oz_azoligi = Membership.objects.get(user=self.admin_user, center=self.center)
        response = self.api("patch", f"/api/memberships/{oz_azoligi.id}/", {"role": "OWNER"})
        self.assertEqual(response.status_code, 403, response.content)
        oz_azoligi.refresh_from_db()
        self.assertEqual(oz_azoligi.role, Membership.Role.ADMIN)


class TeacherScopeTest(ReviewFixBase):
    """O'qituvchi faqat o'zi dars beradigan darslar bilan ishlaydi."""

    def setUp(self):
        super().setUp()
        self.student = make_student(self.center, "Ali", "Valiyev")
        self.boshqa_teacher = make_teacher(self.center, "t2@a.uz", "+998900000012")

    def make_lesson(self, teacher, nom):
        group = make_group(
            self.center,
            self.course,
            self.branch,
            teacher,
            name=nom,
            start_date=self.today - timedelta(days=10),
            end_date=self.today + timedelta(days=10),
        )
        make_enrollment(group, self.student, joined_at=self.today - timedelta(days=5))
        return Lesson.objects.create(
            center=self.center,
            group=group,
            date=self.today,
            start_time="09:00",
            end_time="10:30",
            room=self.room,
            teacher=teacher,
        )

    def davomat(self, lesson):
        return self.as_teacher(
            "post",
            f"/api/lessons/{lesson.id}/attendance/",
            {"items": [{"student": str(self.student.id), "status": "PRESENT"}]},
        )

    def test_r1h_teacher_marks_own_lesson(self):
        response = self.davomat(self.make_lesson(self.teacher, "OZ-GURUH"))
        self.assertEqual(response.status_code, 201, response.content)

    def test_r1i_teacher_cannot_mark_another_teachers_lesson(self):
        response = self.davomat(self.make_lesson(self.boshqa_teacher, "BEGONA-GURUH"))
        self.assertEqual(response.status_code, 403, response.content)

    def test_r1j_teacher_cannot_move_lesson(self):
        lesson = self.make_lesson(self.teacher, "OZ-GURUH")
        response = self.as_teacher(
            "post",
            f"/api/lessons/{lesson.id}/move/",
            {
                "date": str(self.today + timedelta(days=2)),
                "start_time": "14:00",
                "end_time": "15:30",
                "room": str(self.room.id),
            },
        )
        self.assertEqual(response.status_code, 403, response.content)


class GroupStatusTest(ReviewFixBase):
    """2-kamchilik: status PATCH bilan o'zgarib, xizmat mantiqi chetlab o'tilardi."""

    def test_r2a_patch_status_is_ignored(self):
        group = make_group(
            self.center, self.course, self.branch, self.teacher,
            name="ENG-02", start_date=self.start, end_date=self.end,
        )
        make_schedule(group, 0, self.room, "09:00", "10:30")

        response = self.api("patch", f"/api/groups/{group.id}/", {"status": "ACTIVE"})
        self.assertEqual(response.status_code, 200, response.content)

        group.refresh_from_db()
        self.assertEqual(group.status, "PLANNED")
        self.assertEqual(Lesson.objects.filter(group=group).count(), 0)

    def test_r2b_cancel_action_also_cancels_future_lessons(self):
        group = self.active_group()
        self.assertEqual(
            Lesson.objects.filter(group=group, status=Lesson.Status.PLANNED).count(), 2
        )

        response = self.api("post", f"/api/groups/{group.id}/cancel/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["lessons_cancelled"], 2)

        group.refresh_from_db()
        self.assertEqual(group.status, "CANCELLED")
        self.assertEqual(
            Lesson.objects.filter(group=group, status=Lesson.Status.PLANNED).count(), 0
        )

    def test_r2c_cancelled_group_frees_the_room(self):
        """Bekor qilingan guruh darslari endi xonani band qilmaydi."""
        group = self.active_group()
        self.api("post", f"/api/groups/{group.id}/cancel/")

        t2 = make_teacher(self.center, "t2@a.uz", "+998900000012")
        yangi = self.active_group(name="ENG-03", teacher=t2)
        self.assertEqual(Lesson.objects.filter(group=yangi).count(), 2)


class TeacherSwapConflictTest(ReviewFixBase):
    """3-kamchilik: o'qituvchi almashganda ziddiyat tekshirilmasdi."""

    def test_r3_swap_into_conflict_is_rejected(self):
        g1 = self.active_group("ENG-A")
        t2 = make_teacher(self.center, "t2@a.uz", "+998900000012")
        branch2 = make_branch_and_room(self)
        g2 = self.active_group("ENG-B", teacher=t2, room=branch2[1], branch=branch2[0])

        response = self.api("patch", f"/api/groups/{g2.id}/", {"teacher": str(self.teacher.id)})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("qnash", str(response.json()))

        # O'qituvchi ham, darslar ham o'zgarmagan
        g2.refresh_from_db()
        self.assertEqual(g2.teacher_id, t2.id)
        self.assertEqual(
            Lesson.objects.filter(group=g2, teacher=self.teacher).count(), 0
        )
        self.assertEqual(
            Lesson.objects.filter(
                teacher=self.teacher, date=self.start, start_time="09:00",
                status=Lesson.Status.PLANNED,
            ).count(),
            1,
        )

    def test_r3b_swap_without_conflict_still_works(self):
        group = self.active_group("ENG-A")
        t2 = make_teacher(self.center, "t2@a.uz", "+998900000012")

        response = self.api("patch", f"/api/groups/{group.id}/", {"teacher": str(t2.id)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            Lesson.objects.filter(group=group, teacher=t2).count(), 2
        )


def make_branch_and_room(test):
    """Ikkinchi filial va undagi xona."""
    from apps.common.sample_data import make_branch, make_room

    branch = make_branch(test.center, "Yunusobod filiali")
    room = make_room(test.center, branch, "201-xona")
    return branch, room


class DuplicateReturns400Test(ReviewFixBase):
    """4-kamchilik: takroriy yozuv 500 qaytarardi."""

    def test_r4a_duplicate_branch_returns_400(self):
        response = self.api("post", "/api/branches/", {"name": self.branch.name})
        self.assertEqual(response.status_code, 400, response.content)

    def test_r4b_duplicate_membership_returns_400(self):
        response = self.api(
            "post",
            "/api/memberships/",
            {"user": str(self.teacher.user_id), "role": "TEACHER", "started_at": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            Membership.objects.filter(
                user=self.teacher.user, center=self.center, role="TEACHER"
            ).count(),
            1,
        )


class TenantResolutionTest(ReviewFixBase):
    """5- va 6-kamchiliklar: rollarni markaz deb sanash va SUSPENDED markaz."""

    def test_r5_two_roles_in_one_center_is_not_two_centers(self):
        from apps.common.sample_data import make_membership

        make_membership(self.admin_user, self.center, role=Membership.Role.ACCOUNTANT)
        token = get_token(self.client, "admin@a.uz")

        response = self.client.get(
            "/api/branches/", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_r5b_strongest_role_is_used(self):
        """ADMIN + TEACHER bo'lsa ADMIN huquqlari ishlaydi."""
        from apps.common.sample_data import make_membership

        make_membership(self.admin_user, self.center, role=Membership.Role.TEACHER)
        response = self.api("post", "/api/students/", {"first_name": "A", "last_name": "B"})
        self.assertEqual(response.status_code, 201, response.content)

    def test_r6_suspended_center_is_blocked(self):
        self.center.status = "SUSPENDED"
        self.center.save(update_fields=["status"])

        oqish = self.api("get", "/api/branches/")
        yozish = self.api("post", "/api/students/", {"first_name": "A", "last_name": "B"})
        self.assertEqual(oqish.status_code, 403, oqish.content)
        self.assertEqual(yozish.status_code, 403, yozish.content)


class LessonSyncTest(ReviewFixBase):
    """7-kamchilik: jadval va bayram bilan sinxronlik."""

    def test_r7a_topic_survives_schedule_change(self):
        group = self.active_group()
        lesson = Lesson.objects.filter(group=group).order_by("date").first()
        self.api("patch", f"/api/lessons/{lesson.id}/", {"topic": "Present Simple"})

        response = self.api(
            "post",
            f"/api/groups/{group.id}/schedules/",
            {"weekday": 2, "start_time": "09:00", "end_time": "10:30", "room": str(self.room.id)},
        )
        self.assertEqual(response.status_code, 201, response.content)

        qayta = Lesson.objects.get(group=group, date=lesson.date, start_time="09:00")
        self.assertEqual(qayta.topic, "Present Simple")

    def test_r7b_holiday_added_later_removes_the_lesson(self):
        group = self.active_group()
        sana = Lesson.objects.filter(group=group).order_by("date").first().date

        response = self.api(
            "post", "/api/holidays/", {"date": str(sana), "name": "Keyin qo'shilgan bayram"}
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            Lesson.objects.filter(group=group, date=sana, status=Lesson.Status.PLANNED).count(),
            0,
        )

    def test_r7c_moving_a_holiday_restores_lessons(self):
        group = self.active_group()
        sana = Lesson.objects.filter(group=group).order_by("date").first().date

        bayram = self.api("post", "/api/holidays/", {"date": str(sana), "name": "Bayram"}).json()
        self.assertEqual(Lesson.objects.filter(group=group, date=sana).count(), 0)

        # Bayramni boshqa kunga surdik - dars qaytishi kerak
        yangi_sana = sana + timedelta(days=1)
        response = self.api("patch", f"/api/holidays/{bayram['id']}/", {"date": str(yangi_sana)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Lesson.objects.filter(group=group, date=sana).count(), 1)


class HeldLessonTest(ReviewFixBase):
    """8-kamchilik: HELD darsni bekor qilish mumkin edi."""

    def test_r8_held_lesson_cannot_be_cancelled(self):
        group = self.active_group()
        lesson = Lesson.objects.filter(group=group).order_by("date").first()
        lesson.status = Lesson.Status.HELD
        lesson.save(update_fields=["status"])

        response = self.api("patch", f"/api/lessons/{lesson.id}/", {"status": "CANCELLED"})
        self.assertEqual(response.status_code, 400, response.content)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.HELD)

    def test_r8b_planned_lesson_can_be_cancelled(self):
        group = self.active_group()
        lesson = Lesson.objects.filter(group=group).order_by("date").first()

        response = self.api("patch", f"/api/lessons/{lesson.id}/", {"status": "CANCELLED"})
        self.assertEqual(response.status_code, 200, response.content)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.CANCELLED)

    def test_r8c_moved_lesson_cannot_be_cancelled(self):
        group = self.active_group()
        lesson = Lesson.objects.filter(group=group).order_by("date").first()
        lesson.status = Lesson.Status.MOVED
        lesson.save(update_fields=["status"])

        response = self.api("patch", f"/api/lessons/{lesson.id}/", {"status": "CANCELLED"})
        self.assertEqual(response.status_code, 400, response.content)


class PaginationTest(ReviewFixBase):
    """9-kamchilik: ro'yxatlar sahifalanmagan edi."""

    def test_r9_list_endpoints_are_paginated(self):
        group = self.active_group()
        response = self.api("get", "/api/lessons/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        for kalit in ("count", "next", "previous", "results"):
            self.assertIn(kalit, data)
        self.assertEqual(data["count"], 2)

    def test_r9b_page_size_is_capped(self):
        """Katta guruhda ham bitta javobda 50 tadan ko'p dars kelmaydi."""
        group = make_group(
            self.center, self.course, self.branch, self.teacher,
            name="KATTA", start_date=self.start, end_date=self.start + timedelta(days=200),
        )
        make_schedule(group, 0, self.room, "11:00", "12:30")
        make_schedule(group, 2, self.room, "11:00", "12:30")
        self.api("post", f"/api/groups/{group.id}/activate/")

        jami = Lesson.objects.filter(group=group).count()
        self.assertGreater(jami, 50)

        response = self.api("get", f"/api/lessons/?group={group.id}")
        data = response.json()
        self.assertEqual(data["count"], jami)
        self.assertEqual(len(data["results"]), 50)
        self.assertIsNotNone(data["next"])
