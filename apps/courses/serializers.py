"""Kurs, xona, bayram serializerlari."""

from apps.common.serializers import TenantModelSerializer
from apps.courses.models import Course, Holiday, Room

COMMON_READ_ONLY = ["id", "center", "created_at", "updated_at"]


class CourseSerializer(TenantModelSerializer):
    class Meta:
        model = Course
        fields = COMMON_READ_ONLY + [
            "name",
            "duration_months",
            "lessons_per_week",
            "default_price",
            "status",
        ]
        read_only_fields = COMMON_READ_ONLY


class RoomSerializer(TenantModelSerializer):
    tenant_fk_fields = ("branch",)

    class Meta:
        model = Room
        fields = COMMON_READ_ONLY + ["branch", "name", "capacity", "status"]
        read_only_fields = COMMON_READ_ONLY


class HolidaySerializer(TenantModelSerializer):
    class Meta:
        model = Holiday
        fields = COMMON_READ_ONLY + ["date", "name"]
        read_only_fields = COMMON_READ_ONLY
