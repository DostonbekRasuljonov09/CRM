"""Dars va davomat serializerlari."""

from rest_framework import serializers

from apps.common.serializers import TenantModelSerializer
from apps.courses.models import Room
from apps.lessons.models import Attendance, Lesson
from apps.students.models import Student

READ_ONLY = ["id", "center", "created_at", "updated_at"]


def _tekshir_markaz(value, context, nom):
    """Obyekt so'rov markaziga tegishlimi."""
    center = getattr(context.get("request"), "center", None)
    if center is not None and getattr(value, "center_id", None) != center.id:
        raise serializers.ValidationError(f"{nom} boshqa markazga tegishli.")
    return value


class LessonSerializer(TenantModelSerializer):
    """Dars. PATCH orqali faqat `topic` va `status` (CANCELLED) o'zgaradi."""

    group_name = serializers.CharField(source="group.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name", read_only=True
    )

    class Meta:
        model = Lesson
        fields = READ_ONLY + [
            "group",
            "group_name",
            "date",
            "start_time",
            "end_time",
            "room",
            "room_name",
            "teacher",
            "teacher_name",
            "status",
            "topic",
            "moved_to",
        ]
        read_only_fields = READ_ONLY + [
            "group",
            "date",
            "start_time",
            "end_time",
            "room",
            "teacher",
            "moved_to",
        ]

    def validate_status(self, value):
        if value != Lesson.Status.CANCELLED:
            raise serializers.ValidationError(
                "PATCH orqali darsni faqat CANCELLED holatiga o'tkazish mumkin. "
                "Ko'chirish uchun /move/ endpointidan foydalaning."
            )
        # Faqat PLANNED -> CANCELLED. O'tkazilgan darsni bekor qilsak,
        # davomat yozuvlari egasiz qolib 3-bosqichdagi maosh hisobini buzadi.
        if self.instance is not None and self.instance.status != Lesson.Status.PLANNED:
            raise serializers.ValidationError(
                "Faqat rejalashtirilgan darsni bekor qilish mumkin. "
                f"Bu darsning holati: {self.instance.get_status_display()}."
            )
        return value


class MoveLessonSerializer(serializers.Serializer):
    """Darsni ko'chirish uchun kiruvchi ma'lumot."""

    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all())

    def validate_room(self, value):
        return _tekshir_markaz(value, self.context, "Xona")

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError(
                {"end_time": "Tugash vaqti boshlanish vaqtidan keyin bo'lishi shart."}
            )
        return attrs


class AttendanceSerializer(TenantModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = READ_ONLY + [
            "lesson",
            "student",
            "student_name",
            "status",
            "note",
            "marked_by",
            "marked_at",
        ]
        read_only_fields = READ_ONLY + ["lesson", "marked_by", "marked_at"]


class AttendanceItemSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    status = serializers.ChoiceField(choices=Attendance.Status.choices)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)

    def validate_student(self, value):
        return _tekshir_markaz(value, self.context, "O'quvchi")


class AttendanceBulkSerializer(serializers.Serializer):
    """Ommaviy davomat: bitta so'rovda butun guruh."""

    items = AttendanceItemSerializer(many=True, allow_empty=False)
