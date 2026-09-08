"""O'quvchi API testlari (20-test)."""

from apps.common.sample_data import TenantApiTestCase, make_center, make_student
from apps.students.models import Student


class StudentApiTest(TenantApiTestCase):
    def test_20_foreign_student_returns_404(self):
        """20-test: begona markazning o'quvchisi so'ralganda 404."""
        center_b = make_center("B markaz", "b-markaz")
        begona = make_student(center_b, "Begona", "O'quvchi")

        response = self.api("get", f"/api/students/{begona.id}/")
        self.assertEqual(response.status_code, 404, response.content)
        self.assertTrue(Student.objects.filter(pk=begona.pk).exists())

    def test_student_crud_without_delete(self):
        yaratish = self.api(
            "post",
            "/api/students/",
            {"first_name": "Ali", "last_name": "Valiyev", "phone": "+998901234567"},
        )
        self.assertEqual(yaratish.status_code, 201, yaratish.content)
        student_id = yaratish.json()["id"]
        self.assertEqual(yaratish.json()["center"], str(self.center.id))

        # Arxivlash - o'chirish emas
        arxiv = self.api("patch", f"/api/students/{student_id}/", {"status": "ARCHIVED"})
        self.assertEqual(arxiv.status_code, 200, arxiv.content)

        o_chirish = self.api("delete", f"/api/students/{student_id}/")
        self.assertEqual(o_chirish.status_code, 405, o_chirish.content)

    def test_client_center_is_ignored(self):
        center_b = make_center("B markaz", "b-markaz")
        response = self.api(
            "post",
            "/api/students/",
            {"first_name": "Ali", "last_name": "Valiyev", "center": str(center_b.id)},
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["center"], str(self.center.id))
