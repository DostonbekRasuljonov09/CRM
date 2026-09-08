"""Kurs, xona va bayram API testlari."""

from apps.common.sample_data import TenantApiTestCase, make_branch, make_center
from apps.courses.models import Room


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
