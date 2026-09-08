"""Guruh serializerlari."""

from rest_framework import serializers

from apps.common.serializers import TenantModelSerializer
from apps.students.models import Student
from apps.study_groups.models import Group, GroupSchedule, GroupStudent

READ_ONLY = ["id", "center", "created_at", "updated_at"]


class GroupSerializer(TenantModelSerializer):
    tenant_fk_fields = ("course", "branch", "teacher")

    class Meta:
        model = Group
        fields = READ_ONLY + [
            "name",
            "course",
            "branch",
            "teacher",
            "monthly_price",
            "start_date",
            "end_date",
            "max_students",
            "status",
        ]
        read_only_fields = READ_ONLY


class GroupScheduleSerializer(TenantModelSerializer):
    tenant_fk_fields = ("room",)

    class Meta:
        model = GroupSchedule
        fields = READ_ONLY + ["group", "weekday", "start_time", "end_time", "room"]
        # group URL dan olinadi
        read_only_fields = READ_ONLY + ["group"]


class GroupStudentSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)

    class Meta:
        model = GroupStudent
        fields = READ_ONLY + [
            "group",
            "student",
            "student_name",
            "joined_at",
            "left_at",
            "status",
        ]
        read_only_fields = READ_ONLY + ["group"]


class EnrollmentCreateSerializer(serializers.Serializer):
    """Guruhga o'quvchi qo'shish uchun kiruvchi ma'lumot."""

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    joined_at = serializers.DateField(required=False)


class LeaveSerializer(serializers.Serializer):
    """Guruhdan chiqarish uchun kiruvchi ma'lumot."""

    left_at = serializers.DateField(required=False)
