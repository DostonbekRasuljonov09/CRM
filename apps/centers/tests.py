"""Markaz modeli testlari."""

from django.db.models import ProtectedError
from django.test import TestCase

from apps.centers.models import Center
from apps.common.sample_data import make_branch, make_center


class CenterProtectTest(TestCase):
    """11-test: filiallari bor markazni o'chirib bo'lmaydi (PROTECT)."""

    def test_11_center_with_branches_cannot_be_deleted(self):
        center = make_center("A markaz", "a-markaz")
        make_branch(center, "A-1 filial")

        with self.assertRaises(ProtectedError):
            center.delete()

        self.assertTrue(Center.objects.filter(pk=center.pk).exists())

    def test_11b_empty_center_can_be_deleted(self):
        center = make_center("Bo'sh markaz", "bosh-markaz")
        center.delete()
        self.assertFalse(Center.objects.filter(pk=center.pk).exists())
