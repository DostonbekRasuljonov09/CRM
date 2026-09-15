"""Autentifikatsiya va a'zolik testlari."""

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Membership
from apps.common.sample_data import (
    PAROL,
    auth_headers,
    get_token,
    make_branch,
    make_center,
    make_membership,
    make_user,
)


class LoginTest(TestCase):
    """1-test: email + parol bilan login ishlaydi, JWT qaytadi."""

    def setUp(self):
        self.user = make_user("admin@a.uz", "+998900000001")
        self.center = make_center("A markaz", "a-markaz")
        make_membership(self.user, self.center)

    def test_01_login_returns_jwt(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "admin@a.uz", "password": PAROL},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

        # Token bilan /api/me/ ochiladi
        me = self.client.get(
            "/api/me/", headers={"Authorization": f"Bearer {data['access']}"}
        )
        self.assertEqual(me.status_code, 200, me.content)
        self.assertEqual(me.json()["email"], "admin@a.uz")
        self.assertEqual(len(me.json()["memberships"]), 1)

        # Refresh ham ishlaydi
        refresh = self.client.post(
            "/api/auth/refresh/",
            {"refresh": data["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(refresh.status_code, 200, refresh.content)
        self.assertIn("access", refresh.json())

    def test_01b_wrong_password_fails(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "admin@a.uz", "password": "notogri"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)


class MembershipBranchValidationTest(TestCase):
    """12-test: begona markaz filiali qo'shilsa - validatsiya xatosi."""

    def test_12_foreign_branch_rejected(self):
        user = make_user("xodim@a.uz", "+998900000002")
        center_a = make_center("A markaz", "a-markaz")
        center_b = make_center("B markaz", "b-markaz")
        branch_b = make_branch(center_b, "B filial")

        membership = make_membership(user, center_a, role=Membership.Role.TEACHER)
        membership.branches.add(branch_b)

        with self.assertRaises(ValidationError) as ctx:
            membership.full_clean()
        self.assertIn("branches", ctx.exception.message_dict)

    def test_12b_own_branch_accepted(self):
        user = make_user("xodim2@a.uz", "+998900000003")
        center_a = make_center("A markaz", "a-markaz")
        branch_a = make_branch(center_a, "A filial")

        membership = make_membership(user, center_a, role=Membership.Role.TEACHER)
        membership.branches.add(branch_a)

        membership.full_clean()  # xato bo'lmasligi kerak


class MembershipApiBranchValidationTest(TestCase):
    """12-test, API darajasi: begona filial serializer'da ham to'siladi.

    Model clean() save() da avtomatik chaqirilmaydi va M2M .add() da umuman
    ishlamaydi - shuning uchun himoya HTTP yo'lida alohida tekshiriladi.
    """

    def setUp(self):
        self.center_a = make_center("A markaz", "a-markaz")
        self.center_b = make_center("B markaz", "b-markaz")
        self.branch_a = make_branch(self.center_a, "A filial")
        self.branch_b = make_branch(self.center_b, "B filial")

        self.admin = make_user("a.admin@crm.uz", "+998911111111")
        make_membership(self.admin, self.center_a)
        self.token = get_token(self.client, "a.admin@crm.uz")
        self.headers = auth_headers(self.token, self.center_a)

    def test_12c_api_create_rejects_foreign_branch(self):
        xodim = make_user("yangi@crm.uz", "+998955555555")
        response = self.client.post(
            "/api/memberships/",
            {
                "user": str(xodim.id),
                "role": Membership.Role.TEACHER,
                "started_at": "2026-01-01",
                "branches": [str(self.branch_b.id)],
            },
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("branches", response.json())
        self.assertFalse(Membership.objects.filter(user=xodim).exists())

    def test_12d_api_patch_rejects_foreign_branch(self):
        xodim = make_user("yangi2@crm.uz", "+998955555556")
        membership = make_membership(xodim, self.center_a, role=Membership.Role.TEACHER)

        response = self.client.patch(
            f"/api/memberships/{membership.id}/",
            {"branches": [str(self.branch_b.id)]},
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("branches", response.json())

        membership.refresh_from_db()
        self.assertEqual(list(membership.branches.all()), [])

    def test_12e_api_accepts_own_branch(self):
        xodim = make_user("yangi3@crm.uz", "+998955555557")
        response = self.client.post(
            "/api/memberships/",
            {
                "user": str(xodim.id),
                "role": Membership.Role.TEACHER,
                "started_at": "2026-01-01",
                "branches": [str(self.branch_a.id)],
            },
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.content)
        membership = Membership.objects.get(user=xodim)
        self.assertEqual([b.name for b in membership.branches.all()], ["A filial"])


class LoginThrottleTest(TestCase):
    """Login endpointi brute-force'dan himoyalangan (10/min)."""

    def setUp(self):
        cache.clear()
        self.user = make_user("throttle@a.uz", "+998900000055")

    def test_login_is_throttled_after_repeated_attempts(self):
        kodlar = []
        for _ in range(12):
            response = self.client.post(
                "/api/auth/login/",
                {"email": "throttle@a.uz", "password": "notogri"},
                content_type="application/json",
            )
            kodlar.append(response.status_code)

        self.assertIn(401, kodlar, f"kodlar: {kodlar}")
        self.assertIn(429, kodlar, f"Cheklov ishlamadi, kodlar: {kodlar}")
        # Cheklovdan keyin to'g'ri parol ham o'tmaydi
        self.assertEqual(kodlar[-1], 429)
