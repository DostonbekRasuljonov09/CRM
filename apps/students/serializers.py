"""O'quvchi serializeri."""

from apps.common.serializers import TenantModelSerializer
from apps.students.models import Student

READ_ONLY = ["id", "center", "created_at", "updated_at"]


class StudentSerializer(TenantModelSerializer):
    class Meta:
        model = Student
        fields = READ_ONLY + [
            "first_name",
            "last_name",
            "phone",
            "birth_date",
            "parent_name",
            "parent_phone",
            "status",
        ]
        read_only_fields = READ_ONLY
