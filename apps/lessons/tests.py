"""Dars generatsiyasi va ziddiyat testlari (6-12, 20, 22)."""

from datetime import timedelta

from django.utils import timezone

from apps.common.sample_data import (
    TenantApiTestCase,
    make_branch,
    make_center,
    make_course,
    make_group,
    make_holiday,
    make_room,
    make_schedule,
    make_teacher,
)
from apps.lessons.models import Lesson
from apps.lessons.services import generate_lessons
from apps.study_groups.models import Group


class LessonGenerationTest(TenantApiTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        # Kelasi dushanbadan boshlab aniq 2 hafta (14 kun)
        self.start = self.today + timedelta(days=(7 - self.today.weekday()) % 7 or 7)
        self.end = self.start + timedelta(days=13)

        self.group = make_group(
            self.center,
            self.course,
            self.branch,
            self.teacher,
            name="ENG-01",
            start_date=self.start,
            end_date=self.end,
        )
        make_schedule(self.group, 0, self.room, "09:00", "10:30")  # Dushanba
        make_schedule(self.group, 2, self.room, "09:00", "10:30")  # Chorshanba

    def activate(self, group=None):
        group = group or self.group
        return self.api("post", f"/api/groups/{group.id}/activate/")

    def test_06_activation_generates_exact_lessons(self):
        """6-test: guruh ACTIVE bo'lganda darslar soni aniq to'g'ri."""
        response = self.activate()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["lessons_created"], 4)

        sanalar = list(
            Lesson.objects.filter(group=self.group).order_by("date").values_list("date", flat=True)
        )
        self.assertEqual(
            sanalar,
            [
                self.start,
                self.start + timedelta(days=2),
                self.start + timedelta(days=7),
                self.start + timedelta(days=9),
            ],
        )
        self.assertEqual(Group.objects.get(pk=self.group.pk).status, Group.Status.ACTIVE)

    def test_07_holiday_is_skipped(self):
        """7-test: bayram kuniga dars yaratilmaydi."""
        make_holiday(self.center, self.start, "Navro'z")

        response = self.activate()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["lessons_created"], 3)
        self.assertFalse(Lesson.objects.filter(group=self.group, date=self.start).exists())

    def test_22_generation_is_idempotent(self):
        """22-test: ikki marta chaqirilsa darslar soni o'zgarmaydi."""
        self.activate()
        birinchi = list(
            Lesson.objects.filter(group=self.group).order_by("date").values_list("date", flat=True)
        )

        self.group.refresh_from_db()
        generate_lessons(self.group)

        ikkinchi = list(
            Lesson.objects.filter(group=self.group).order_by("date").values_list("date", flat=True)
        )
        self.assertEqual(birinchi, ikkinchi)
        self.assertEqual(len(ikkinchi), 4)

    def test_08_room_conflict_blocks_everything(self):
        """8-test: bir xonada ustma-ust dars - 400 va birorta dars yaratilmaydi."""
        self.activate()

        teacher2 = make_teacher(self.center, "teacher2@a.uz", "+998900000012")
        group2 = make_group(
            self.center, self.course, self.branch, teacher2, name="ENG-02",
            start_date=self.start, end_date=self.end,
        )
        make_schedule(group2, 0, self.room, "09:00", "10:30")

        response = self.activate(group2)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("xona", str(response.json()))
        self.assertEqual(Lesson.objects.filter(group=group2).count(), 0)
        # Atomic: status ham qaytib PLANNED bo'lib qoladi
        self.assertEqual(Group.objects.get(pk=group2.pk).status, Group.Status.PLANNED)

    def test_09_teacher_conflict_across_branches(self):
        """9-test: bir o'qituvchida ustma-ust dars - boshqa filialda bo'lsa ham."""
        self.activate()

        branch2 = make_branch(self.center, "Yunusobod filiali")
        room2 = make_room(self.center, branch2, "201-xona")
        group2 = make_group(
            self.center, self.course, branch2, self.teacher, name="ENG-03",
            start_date=self.start, end_date=self.end,
        )
        make_schedule(group2, 0, room2, "09:00", "10:30")

        response = self.activate(group2)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("o'qituvchi", str(response.json()))
        self.assertEqual(Lesson.objects.filter(group=group2).count(), 0)

    def test_10_cancelled_lesson_is_not_a_conflict(self):
        """10-test: CANCELLED dars ziddiyat sifatida hisoblanmaydi."""
        self.activate()
        Lesson.objects.filter(group=self.group).update(status=Lesson.Status.CANCELLED)

        teacher2 = make_teacher(self.center, "teacher2@a.uz", "+998900000012")
        group2 = make_group(
            self.center, self.course, self.branch, teacher2, name="ENG-02",
            start_date=self.start, end_date=self.end,
        )
        make_schedule(group2, 0, self.room, "09:00", "10:30")

        response = self.activate(group2)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Lesson.objects.filter(group=group2).count(), 2)

    def test_11_schedule_change_keeps_held_lessons(self):
        """11-test: jadval o'zgarganda PLANNED qayta yaratiladi, HELD tegilmaydi."""
        self.activate()

        held = Lesson.objects.filter(group=self.group).order_by("date").first()
        held.status = Lesson.Status.HELD
        held.save(update_fields=["status"])
        held_pk, held_date = held.pk, held.date

        # Jumaga yangi jadval qo'shamiz -> qayta generatsiya
        response = self.api(
            "post",
            f"/api/groups/{self.group.id}/schedules/",
            {"weekday": 4, "start_time": "09:00", "end_time": "10:30", "room": str(self.room.id)},
        )
        self.assertEqual(response.status_code, 201, response.content)

        # HELD dars o'sha-o'sha (pk ham o'zgarmagan)
        yangilangan = Lesson.objects.get(pk=held_pk)
        self.assertEqual(yangilangan.status, Lesson.Status.HELD)
        self.assertEqual(yangilangan.date, held_date)

        # 2 dushanba + 2 chorshanba + 2 juma = 6
        self.assertEqual(Lesson.objects.filter(group=self.group).count(), 6)
        self.assertEqual(
            Lesson.objects.filter(group=self.group, date=held_date).count(), 1
        )

    def test_12_teacher_change_updates_only_future_planned(self):
        """12-test: o'qituvchi almashganda faqat kelajakdagi PLANNED darslar yangilanadi."""
        self.activate()

        held = Lesson.objects.filter(group=self.group).order_by("date").first()
        held.status = Lesson.Status.HELD
        held.save(update_fields=["status"])

        # O'tgan sanadagi PLANNED dars
        otgan = Lesson.objects.create(
            center=self.center,
            group=self.group,
            date=self.today - timedelta(days=3),
            start_time="09:00",
            end_time="10:30",
            room=self.room,
            teacher=self.teacher,
            status=Lesson.Status.PLANNED,
        )

        teacher2 = make_teacher(self.center, "teacher2@a.uz", "+998900000012")
        response = self.api("patch", f"/api/groups/{self.group.id}/", {"teacher": str(teacher2.id)})
        self.assertEqual(response.status_code, 200, response.content)

        kelajak = Lesson.objects.filter(
            group=self.group, status=Lesson.Status.PLANNED, date__gte=self.today
        )
        self.assertEqual(kelajak.count(), 3)
        for lesson in kelajak:
            self.assertEqual(lesson.teacher_id, teacher2.id)

        # HELD va o'tgan darslar tegilmagan
        held.refresh_from_db()
        otgan.refresh_from_db()
        self.assertEqual(held.teacher_id, self.teacher.id)
        self.assertEqual(otgan.teacher_id, self.teacher.id)

    def test_20_foreign_lesson_returns_404(self):
        """20-test: begona markazning darsi so'ralganda 404."""
        center_b = make_center("B markaz", "b-markaz")
        branch_b = make_branch(center_b, "B filial")
        course_b = make_course(center_b, name="B kurs")
        room_b = make_room(center_b, branch_b, "B-101")
        teacher_b = make_teacher(center_b, "b.teacher@b.uz", "+998900000098")
        group_b = make_group(
            center_b, course_b, branch_b, teacher_b, name="B-GURUH",
            start_date=self.start, end_date=self.end,
        )
        begona = Lesson.objects.create(
            center=center_b, group=group_b, date=self.start,
            start_time="09:00", end_time="10:30", room=room_b, teacher=teacher_b,
        )

        response = self.api("get", f"/api/lessons/{begona.id}/")
        self.assertEqual(response.status_code, 404, response.content)
        self.assertTrue(Lesson.objects.filter(pk=begona.pk).exists())

    def test_20b_lesson_list_is_filtered_by_center_and_params(self):
        self.activate()
        hammasi = self.api("get", "/api/lessons/")
        self.assertEqual(hammasi.status_code, 200)
        self.assertEqual(len(hammasi.json()), 4)

        filtrlangan = self.api(
            "get", f"/api/lessons/?group={self.group.id}&date_from={self.start + timedelta(days=7)}"
        )
        self.assertEqual(len(filtrlangan.json()), 2)

    def test_20c_lesson_cannot_be_created_via_api(self):
        """Darslar faqat generatsiya orqali paydo bo'ladi."""
        response = self.api("post", "/api/lessons/", {"date": str(self.start)})
        self.assertEqual(response.status_code, 405, response.content)
