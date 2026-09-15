"""Markazlar ilovasi serializerlari."""

from rest_framework import serializers

from apps.common.serializers import ValidatedModelSerializer
from apps.centers.models import Branch, Center


class CenterShortSerializer(serializers.ModelSerializer):
    """Markaz haqida qisqa ma'lumot (faqat o'qish uchun)."""

    class Meta:
        model = Center
        fields = ["id", "name", "slug", "status"]
        read_only_fields = fields


class BranchSerializer(ValidatedModelSerializer):
    """Filial. center faqat o'qish uchun - u serverda o'rnatiladi.

    ValidatedModelSerializer full_clean() ni chaqiradi: takroriy nom
    (center, name) 500 emas, 400 qaytaradi.
    """

    class Meta:
        model = Branch
        fields = [
            "id",
            "center",
            "name",
            "address",
            "phone",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "center", "created_at", "updated_at"]
