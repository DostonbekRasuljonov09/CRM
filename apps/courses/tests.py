"""Kurs, xona va bayram API testlari."""

from datetime import timedelta

from django.utils import timezone

from apps.common.sample_data import (
    TenantApiTestCase,
    make_branch,
    make_center,
    make_group,
    make_schedule,
    make_teacher,
)
from apps.courses.models import Holiday, Room
from apps.lessons.models import Lesson


class CourseApiTest(TenantApiTestCase):
    def test_course_created_via_api(self):
        response = self.api(
            "post",
            "/api/courses/",
            {
                "name": "Matematika",
                "duration_months": 9,
                "lessons_per_week": 3,
                "default_price": "450000.00",
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["center"], str(self.center.id))

    def test_duplicate_course_name_in_center_rejected(self):
        payload = {
            "name": self.course.name,
            "duration_months": 3,
            "lessons_per_week": 2,
            "default_price": "100000.00",
        }
        response = self.api("post", "/api/courses/", payload)
        self.assertEqual(response.status_code, 400, response.content)

    def test_room_from_foreign_branch_rejected(self):
        center_b = make_center("B markaz", "b-markaz")
        branch_b = make_branch(center_b, "B filial")

        response = self.api(
            "post", "/api/rooms/", {"branch": str(branch_b.id), "name": "X-1", "capacity": 10}
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("branch", response.json())
        self.assertFalse(Room.objects.filter(name="X-1").exists())

    def test_holiday_created_and_unique_per_center(self):
        birinchi = self.api("post", "/api/holidays/", {"date": "2027-03-21", "name": "Navro'z"})
        self.assertEqual(birinchi.status_code, 201, birinchi.content)

        ikkinchi = self.api("post", "/api/holidays/", {"date": "2027-03-21", "name": "Boshqa nom"})
        self.assertEqual(ikkinchi.status_code, 400, ikkinchi.content)


class HolidayAtomicityTest(TenantApiTestCase):
    """5-muammo: bayram sanasi 400 xatoda ham saqlanib qolardi."""

    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.start = self.today + timedelta(days=(7 - self.today.weekday()) % 7 or 7)
        self.end = self.start + timedelta(days=13)

    def faol_guruh(self, nom, teacher, weekday, start, end):
        group = make_group(
            self.center,
            self.course,
            self.branch,
            teacher,
            name=nom,
            start_date=self.start,
            end_date=self.end,
        )
        make_schedule(group, weekday, self.room, start, end)
        javob = self.api("post", f"/api/groups/{group.id}/activate/")
        self.assertEqual(javob.status_code, 200, javob.content)
        return group

    def test_i5_holiday_date_rolls_back_on_conflict(self):
        # 1. A guruh faol: dushanba 09:00-10:30, 101-xona
        group_a = self.faol_guruh("A-GURUH", self.teacher, 0, "09:00", "10:30")
        x_kuni = self.start
        self.assertEqual(Lesson.objects.filter(group=group_a, date=x_kuni).count(), 1)

        # 2. X kuniga bayram qo'shiladi - A ning o'sha kungi darsi olib tashlanadi
        bayram = self.api(
            "post", "/api/holidays/", {"date": str(x_kuni), "name": "Bayram"}
        ).json()
        self.assertEqual(Lesson.objects.filter(group=group_a, date=x_kuni).count(), 0)

        # 3. B guruhining darsi X kuni 09:00, 101-xonaga ko'chiriladi
        teacher2 = make_teacher(self.center, "t2@a.uz", "+998900000012")
        group_b = self.faol_guruh("B-GURUH", teacher2, 2, "14:00", "15:30")
        b_dars = Lesson.objects.filter(group=group_b).order_by("date").first()

        kochirish = self.api(
            "post",
            f"/api/lessons/{b_dars.id}/move/",
            {
                "date": str(x_kuni),
                "start_time": "09:00",
                "end_time": "10:30",
                "room": str(self.room.id),
            },
        )
        self.assertEqual(kochirish.status_code, 201, kochirish.content)

        darslar_soni = Lesson.objects.count()

        # 4. Bayram X+1 ga suriladi -> A ning darsi qaytadi va B niki bilan to'qnashadi
        response = self.api(
            "patch",
            f"/api/holidays/{bayram['id']}/",
            {"date": str(x_kuni + timedelta(days=1))},
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("qnash", str(response.json()))

        # Bayram sanasi ham, darslar ham oldingi holatida qoldi
        self.assertEqual(Holiday.objects.get(pk=bayram["id"]).date, x_kuni)
        self.assertEqual(Lesson.objects.count(), darslar_soni)
        self.assertEqual(Lesson.objects.filter(group=group_a, date=x_kuni).count(), 0)

    def test_i5b_holiday_move_without_conflict_still_works(self):
        group = self.faol_guruh("A-GURUH", self.teacher, 0, "09:00", "10:30")
        x_kuni = self.start

        bayram = self.api(
            "post", "/api/holidays/", {"date": str(x_kuni), "name": "Bayram"}
        ).json()
        self.assertEqual(Lesson.objects.filter(group=group, date=x_kuni).count(), 0)

        response = self.api(
            "patch",
            f"/api/holidays/{bayram['id']}/",
            {"date": str(x_kuni + timedelta(days=7))},
        )
        self.assertEqual(response.status_code, 200, response.content)
        # Eski sanaga dars qaytdi, yangi sanadagisi olib tashlandi
        self.assertEqual(Lesson.objects.filter(group=group, date=x_kuni).count(), 1)
        self.assertEqual(
            Lesson.objects.filter(group=group, date=x_kuni + timedelta(days=7)).count(), 0
        )
