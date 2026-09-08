"""Audit jurnali testlari."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.common.sample_data import (
    auth_headers,
    get_token,
    make_branch,
    make_center,
    make_membership,
    make_user,
)


class AuditWriteTest(TestCase):
    """8-test: filial o'zgartirilganda faqat o'zgargan maydon yoziladi."""

    def setUp(self):
        self.center = make_center("A markaz", "a-markaz")
        self.branch = make_branch(
            self.center, "Eski nom", address="Toshkent", phone="+998712000000"
        )
        self.user = make_user("a.admin@crm.uz", "+998911111111")
        make_membership(self.user, self.center)
        self.token = get_token(self.client, "a.admin@crm.uz")

    def test_08_update_writes_only_changed_fields(self):
        response = self.client.patch(
            f"/api/branches/{self.branch.id}/",
            {"name": "Yangi nom"},
            content_type="application/json",
            headers=auth_headers(self.token, self.center),
        )
        self.assertEqual(response.status_code, 200, response.content)

        log = AuditLog.objects.get(
            object_id=str(self.branch.id), action=AuditLog.Action.UPDATE
        )
        self.assertEqual(log.object_type, "centers.Branch")
        self.assertEqual(log.center_id, self.center.id)
        self.assertEqual(log.user_id, self.user.id)
        # Faqat o'zgargan maydon - address va phone yo'q
        self.assertEqual(log.old_values, {"name": "Eski nom"})
        self.assertEqual(log.new_values, {"name": "Yangi nom"})

    def test_08b_status_change_is_logged(self):
        self.client.patch(
            f"/api/branches/{self.branch.id}/",
            {"status": "CLOSED"},
            content_type="application/json",
            headers=auth_headers(self.token, self.center),
        )
        log = AuditLog.objects.get(
            object_id=str(self.branch.id), action=AuditLog.Action.UPDATE
        )
        self.assertEqual(log.old_values, {"status": "ACTIVE"})
        self.assertEqual(log.new_values, {"status": "CLOSED"})

    def test_08c_create_is_logged(self):
        response = self.client.post(
            "/api/branches/",
            {"name": "Ikkinchi filial"},
            content_type="application/json",
            headers=auth_headers(self.token, self.center),
        )
        self.assertEqual(response.status_code, 201, response.content)
        log = AuditLog.objects.get(
            object_id=response.json()["id"], action=AuditLog.Action.CREATE
        )
        self.assertEqual(log.new_values["name"], "Ikkinchi filial")
        self.assertIsNone(log.old_values)

    def test_08d_membership_role_change_is_logged(self):
        xodim = make_user("oqituvchi@crm.uz", "+998933333333")
        membership = make_membership(
            xodim, self.center, role="TEACHER"
        )
        response = self.client.patch(
            f"/api/memberships/{membership.id}/",
            {"role": "ADMIN"},
            content_type="application/json",
            headers=auth_headers(self.token, self.center),
        )
        self.assertEqual(response.status_code, 200, response.content)
        log = AuditLog.objects.get(
            object_id=str(membership.id), action=AuditLog.Action.UPDATE
        )
        self.assertEqual(log.object_type, "accounts.Membership")
        self.assertEqual(log.old_values, {"role": "TEACHER"})
        self.assertEqual(log.new_values, {"role": "ADMIN"})


    def test_08e_date_field_is_stored_as_text(self):
        """Sana (va kelajakda Decimal) JSONField ga matn sifatida yoziladi."""
        xodim = make_user("sanachi@crm.uz", "+998944444444")
        membership = make_membership(xodim, self.center, role="TEACHER")
        response = self.client.patch(
            f"/api/memberships/{membership.id}/",
            {"started_at": "2026-03-15"},
            content_type="application/json",
            headers=auth_headers(self.token, self.center),
        )
        self.assertEqual(response.status_code, 200, response.content)
        log = AuditLog.objects.get(
            object_id=str(membership.id), action=AuditLog.Action.UPDATE
        )
        self.assertEqual(log.old_values, {"started_at": "2026-01-01"})
        self.assertEqual(log.new_values, {"started_at": "2026-03-15"})
        # Bazadan qayta o'qilganda ham buzilmaydi
        log.refresh_from_db()
        self.assertEqual(log.new_values["started_at"], "2026-03-15")


class AuditImmutabilityTest(TestCase):
    """9- va 10-testlar: audit yozuvi o'zgarmas."""

    def setUp(self):
        self.center = make_center("A markaz", "a-markaz")
        self.branch = make_branch(self.center, "A-1 filial")
        self.user = make_user("a.admin@crm.uz", "+998911111111")
        self.log = log_action(
            center=self.center,
            user=self.user,
            action=AuditLog.Action.CREATE,
            instance=self.branch,
            new_values={"name": "A-1 filial"},
        )

    def test_09_existing_log_cannot_be_changed(self):
        log = AuditLog.objects.get(pk=self.log.pk)
        log.action = AuditLog.Action.DELETE
        with self.assertRaises(ValidationError):
            log.save()

        # Bazada eski qiymat qoldi
        self.assertEqual(
            AuditLog.objects.get(pk=self.log.pk).action, AuditLog.Action.CREATE
        )

    def test_10_log_cannot_be_deleted(self):
        log = AuditLog.objects.get(pk=self.log.pk)
        with self.assertRaises(ValidationError):
            log.delete()

        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=self.log.pk).delete()

        self.assertTrue(AuditLog.objects.filter(pk=self.log.pk).exists())

    def test_09b_queryset_update_is_blocked(self):
        """QuerySet.update() model save() ni chaqirmaydi - alohida to'silishi shart."""
        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=self.log.pk).update(action=AuditLog.Action.DELETE)

        self.assertEqual(
            AuditLog.objects.get(pk=self.log.pk).action, AuditLog.Action.CREATE
        )

    def test_09c_bulk_update_is_blocked(self):
        """bulk_update() ham update() ustida ishlaydi - u ham yopiq."""
        log = AuditLog.objects.get(pk=self.log.pk)
        log.ip_address = "9.9.9.9"
        # bulk_update ichkarida atomic(savepoint=False) ishlatadi - istisnodan keyin
        # tranzaksiyani ishlatish uchun o'z savepoint'imiz kerak
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                AuditLog.objects.bulk_update([log], ["ip_address"])

        self.assertIsNone(AuditLog.objects.get(pk=self.log.pk).ip_address)
