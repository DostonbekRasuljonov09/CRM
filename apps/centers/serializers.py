"""Markazlar ilovasi serializerlari."""

from rest_framework import serializers

from apps.centers.models import Branch, Center


class CenterShortSerializer(serializers.ModelSerializer):
    """Markaz haqida qisqa ma'lumot (faqat o'qish uchun)."""

    class Meta:
        model = Center
        fields = ["id", "name", "slug", "status"]
        read_only_fields = fields


class BranchSerializer(serializers.ModelSerializer):
    """Filial. center faqat o'qish uchun - u serverda o'rnatiladi."""

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
