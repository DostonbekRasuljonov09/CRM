"""Autentifikatsiya va a'zolik testlari."""

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Membership
from apps.accounts.services import guard_last_owner
from apps.common.sample_data import (
    PAROL,
    TenantApiTestCase,
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


class MembershipRoleHierarchyTest(TenantApiTestCase):
    """1-muammo: ADMIN OWNER huquqini egallab olardi.

    Rol ierarxiyasi: OWNER barcha rollarni boshqaradi, ADMIN faqat
    TEACHER va ACCOUNTANT ni.
    """

    def setUp(self):
        super().setUp()
        self.owner_user = make_user("owner@a.uz", "+998900000001")
        self.owner = make_membership(
            self.owner_user, self.center, role=Membership.Role.OWNER
        )
        self.admin = Membership.objects.get(user=self.admin_user, center=self.center)
        self.owner_headers = auth_headers(
            get_token(self.client, "owner@a.uz"), self.center
        )

    def as_owner(self, method, url, data=None):
        kwargs = {"headers": self.owner_headers}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(self.client, method)(url, **kwargs)

    # --- (a) ADMIN o'ziga OWNER a'zoligi yaratadi ---
    def test_i1a_admin_cannot_create_owner_membership(self):
        response = self.api(
            "post",
            "/api/memberships/",
            {"user": str(self.admin_user.id), "role": "OWNER", "started_at": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(
            Membership.objects.filter(
                user=self.admin_user, center=self.center, role=Membership.Role.OWNER
            ).exists()
        )

    # --- (b) ADMIN OWNER'ni faolsizlantiradi ---
    def test_i1b_admin_cannot_deactivate_owner(self):
        response = self.api("patch", f"/api/memberships/{self.owner.id}/", {"status": "INACTIVE"})
        self.assertEqual(response.status_code, 403, response.content)

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.status, Membership.Status.ACTIVE)
        # OWNER hali ham ishlay oladi
        self.assertEqual(self.as_owner("get", "/api/branches/").status_code, 200)

    # --- (c) ADMIN OWNER a'zoligini o'ziga o'tkazadi ---
    def test_i1c_admin_cannot_reassign_owner_membership(self):
        response = self.api(
            "patch", f"/api/memberships/{self.owner.id}/", {"user": str(self.admin_user.id)}
        )
        self.assertEqual(response.status_code, 403, response.content)

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.user_id, self.owner_user.id)

    def test_i1d_admin_cannot_create_or_promote_admin(self):
        boshqa = make_user("yangi@a.uz", "+998900000078")

        yaratish = self.api(
            "post",
            "/api/memberships/",
            {"user": str(boshqa.id), "role": "ADMIN", "started_at": "2026-01-01"},
        )
        self.assertEqual(yaratish.status_code, 403, yaratish.content)

        # TEACHER ni ADMIN ga ko'tarish ham yopiq
        oqituvchi = make_membership(boshqa, self.center, role=Membership.Role.TEACHER)
        kotarish = self.api("patch", f"/api/memberships/{oqituvchi.id}/", {"role": "ADMIN"})
        self.assertEqual(kotarish.status_code, 403, kotarish.content)

        oqituvchi.refresh_from_db()
        self.assertEqual(oqituvchi.role, Membership.Role.TEACHER)

    def test_i1e_admin_cannot_touch_another_admin(self):
        boshqa = make_user("admin2@a.uz", "+998900000079")
        boshqa_admin = make_membership(boshqa, self.center, role=Membership.Role.ADMIN)

        response = self.api(
            "patch", f"/api/memberships/{boshqa_admin.id}/", {"status": "INACTIVE"}
        )
        self.assertEqual(response.status_code, 403, response.content)
        boshqa_admin.refresh_from_db()
        self.assertEqual(boshqa_admin.status, Membership.Status.ACTIVE)

    def test_i1f_admin_can_manage_teacher_and_accountant(self):
        for index, rol in enumerate(("TEACHER", "ACCOUNTANT")):
            xodim = make_user(f"xodim{index}@a.uz", f"+99890000008{index}")
            response = self.api(
                "post",
                "/api/memberships/",
                {"user": str(xodim.id), "role": rol, "started_at": "2026-01-01"},
            )
            self.assertEqual(response.status_code, 201, f"{rol}: {response.content}")

    def test_i1g_owner_can_add_another_owner(self):
        boshqa = make_user("owner2@a.uz", "+998900000002")
        response = self.as_owner(
            "post",
            "/api/memberships/",
            {"user": str(boshqa.id), "role": "OWNER", "started_at": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            Membership.objects.filter(
                user=boshqa, center=self.center, role=Membership.Role.OWNER
            ).exists()
        )

    def test_i1h_owner_can_demote_another_owner_but_not_the_last(self):
        boshqa = make_user("owner2@a.uz", "+998900000002")
        ikkinchi = make_membership(boshqa, self.center, role=Membership.Role.OWNER)

        # Ikkita OWNER bor - birini tushirish mumkin
        tushirish = self.as_owner(
            "patch", f"/api/memberships/{ikkinchi.id}/", {"role": "ADMIN"}
        )
        self.assertEqual(tushirish.status_code, 200, tushirish.content)

        # Endi bitta OWNER qoldi va uni hech kim faolsizlantira olmaydi
        ozini = self.as_owner(
            "patch", f"/api/memberships/{self.owner.id}/", {"status": "INACTIVE"}
        )
        self.assertEqual(ozini.status_code, 403, ozini.content)
        self.assertEqual(
            Membership.objects.filter(
                center=self.center,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
            ).count(),
            1,
        )


class LastOwnerGuardTest(TestCase):
    """`guard_last_owner` qoidasi - himoyaning ikkinchi qatlami.

    API orqali bu holatga tushib bo'lmaydi (o'z qatoriga tegish va
    ierarxiya to'sadi), shuning uchun qoida to'g'ridan-to'g'ri sinaladi.
    """

    def setUp(self):
        self.center = make_center("A markaz", "a-markaz")
        self.owner = make_membership(
            make_user("owner@a.uz", "+998900000001"),
            self.center,
            role=Membership.Role.OWNER,
        )

    def test_last_active_owner_cannot_be_deactivated(self):
        with self.assertRaises(ValidationError):
            guard_last_owner(self.owner, yangi_status=Membership.Status.INACTIVE)

    def test_last_active_owner_cannot_be_demoted(self):
        with self.assertRaises(ValidationError):
            guard_last_owner(self.owner, yangi_role=Membership.Role.ADMIN)

    def test_owner_can_be_demoted_when_another_owner_stays(self):
        make_membership(
            make_user("owner2@a.uz", "+998900000002"),
            self.center,
            role=Membership.Role.OWNER,
        )
        # Xato ko'tarilmasligi kerak
        guard_last_owner(self.owner, yangi_role=Membership.Role.ADMIN)

    def test_non_owner_rows_are_not_guarded(self):
        oqituvchi = make_membership(
            make_user("teacher@a.uz", "+998900000003"),
            self.center,
            role=Membership.Role.TEACHER,
        )
        guard_last_owner(oqituvchi, yangi_status=Membership.Status.INACTIVE)


class LoginThrottleSpoofTest(TestCase):
    """2-muammo: soxta `X-Forwarded-For` bilan cheklovni aylanib o'tish."""

    def setUp(self):
        cache.clear()
        make_user("spoof@a.uz", "+998900000056")

    def urinish(self, headers=None):
        return self.client.post(
            "/api/auth/login/",
            {"email": "spoof@a.uz", "password": "notogri"},
            content_type="application/json",
            headers=headers or {},
        )

    def test_spoofed_forwarded_for_cannot_bypass_throttle(self):
        kodlar = [
            self.urinish({"X-Forwarded-For": f"10.0.0.{index + 1}"}).status_code
            for index in range(15)
        ]
        self.assertIn(429, kodlar, f"Soxta IP cheklovni aylanib o'tdi: {kodlar}")
        self.assertEqual(kodlar[-1], 429, f"kodlar: {kodlar}")

    def test_forwarded_for_chain_is_also_ignored(self):
        """Bir nechta IP dan iborat zanjir ham cheklovni buzmaydi."""
        kodlar = [
            self.urinish(
                {"X-Forwarded-For": f"10.0.0.{index + 1}, 172.16.0.{index + 1}"}
            ).status_code
            for index in range(15)
        ]
        self.assertIn(429, kodlar, f"Zanjir cheklovni aylanib o'tdi: {kodlar}")
