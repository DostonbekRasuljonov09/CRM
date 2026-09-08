"""Tenant (markaz) ajratish testlari."""

from django.test import TestCase

from apps.accounts.models import Membership
from apps.centers.models import Branch
from apps.common.sample_data import (
    auth_headers,
    get_token,
    make_branch,
    make_center,
    make_membership,
    make_user,
)


class TenantIsolationTest(TestCase):
    def setUp(self):
        self.center_a = make_center("A markaz", "a-markaz")
        self.center_b = make_center("B markaz", "b-markaz")

        self.branch_a = make_branch(self.center_a, "A-1 filial")
        self.branch_b = make_branch(self.center_b, "B-1 filial")

        self.user_a = make_user("a.admin@crm.uz", "+998911111111")
        make_membership(self.user_a, self.center_a)
        self.token_a = get_token(self.client, "a.admin@crm.uz")

    def test_02_foreign_branch_returns_404(self):
        """2-test: A markaz foydalanuvchisi B filialini so'rasa - 404."""
        response = self.client.get(
            f"/api/branches/{self.branch_b.id}/",
            headers=auth_headers(self.token_a, self.center_a),
        )
        self.assertEqual(response.status_code, 404, response.content)

        # O'z filiali esa ochiladi
        ok = self.client.get(
            f"/api/branches/{self.branch_a.id}/",
            headers=auth_headers(self.token_a, self.center_a),
        )
        self.assertEqual(ok.status_code, 200, ok.content)

        # 404 obyekt yo'qligidan emas - B filial bazada hali ham turibdi
        self.assertTrue(Branch.objects.filter(pk=self.branch_b.pk).exists())

    def test_02b_list_shows_only_own_center(self):
        response = self.client.get(
            "/api/branches/", headers=auth_headers(self.token_a, self.center_a)
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()]
        self.assertEqual(ids, [str(self.branch_a.id)])

    def test_03_multiple_memberships_without_header_returns_400(self):
        """3-test: bir nechta a'zolik + sarlavhasiz so'rov - 400."""
        make_membership(self.user_a, self.center_b, role=Membership.Role.TEACHER)

        response = self.client.get(
            "/api/branches/", headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(response.status_code, 400, response.content)
        data = response.json()
        self.assertIn("centers", data)
        self.assertEqual(len(data["centers"]), 2)
        self.assertEqual(
            sorted(c["slug"] for c in data["centers"]), ["a-markaz", "b-markaz"]
        )

    def test_04_single_membership_without_header_returns_200(self):
        """4-test: bitta a'zolik + sarlavhasiz so'rov - 200."""
        response = self.client.get(
            "/api/branches/", headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()), 1)

    def test_05_inactive_membership_returns_403(self):
        """5-test: INACTIVE a'zolik bilan so'rov - 403."""
        user = make_user("nofaol@crm.uz", "+998922222222")
        make_membership(user, self.center_a, status=Membership.Status.INACTIVE)
        token = get_token(self.client, "nofaol@crm.uz")

        without_header = self.client.get(
            "/api/branches/", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(without_header.status_code, 403, without_header.content)

        with_header = self.client.get(
            "/api/branches/", headers=auth_headers(token, self.center_a)
        )
        self.assertEqual(with_header.status_code, 403, with_header.content)

    def test_06_client_center_is_ignored_on_create(self):
        """6-test: mijoz yuborgan begona center e'tiborsiz qoldiriladi."""
        response = self.client.post(
            "/api/branches/",
            {
                "name": "Yangi filial",
                "address": "Toshkent",
                "phone": "+998712000000",
                "center": str(self.center_b.id),
            },
            content_type="application/json",
            headers=auth_headers(self.token_a, self.center_a),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["center"], str(self.center_a.id))

        branch = Branch.objects.get(name="Yangi filial")
        self.assertEqual(branch.center_id, self.center_a.id)

    def test_07_user_in_two_centers_can_reach_both(self):
        """7-test: bitta foydalanuvchi ikki markazda faol va ikkalasiga kiradi."""
        make_membership(self.user_a, self.center_b, role=Membership.Role.TEACHER)

        response_a = self.client.get(
            "/api/branches/", headers=auth_headers(self.token_a, self.center_a)
        )
        self.assertEqual(response_a.status_code, 200, response_a.content)
        self.assertEqual(
            [row["id"] for row in response_a.json()], [str(self.branch_a.id)]
        )

        response_b = self.client.get(
            "/api/branches/", headers=auth_headers(self.token_a, self.center_b)
        )
        self.assertEqual(response_b.status_code, 200, response_b.content)
        self.assertEqual(
            [row["id"] for row in response_b.json()], [str(self.branch_b.id)]
        )

        me = self.client.get(
            "/api/me/", headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(len(me.json()["memberships"]), 2)

    def test_07b_delete_method_is_not_allowed(self):
        """DELETE hech qayerda yo'q - status orqali arxivlanadi."""
        response = self.client.delete(
            f"/api/branches/{self.branch_a.id}/",
            headers=auth_headers(self.token_a, self.center_a),
        )
        self.assertEqual(response.status_code, 405, response.content)
