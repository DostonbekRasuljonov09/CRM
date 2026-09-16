"""Dars API'si."""

from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.common.utils import client_ip
from apps.common.viewsets import TenantReadUpdateViewSet
from apps.lessons.models import Attendance, Lesson
from apps.lessons.serializers import (
    AttendanceBulkSerializer,
    AttendanceSerializer,
    LessonSerializer,
    MoveLessonSerializer,
)
from apps.lessons.services import mark_attendance, move_lesson


class LessonViewSet(TenantReadUpdateViewSet):
    """
    Darslar. Yaratish yo'q - darslar jadval asosida generatsiya qilinadi.
    PATCH orqali faqat `topic` va `status` (CANCELLED) o'zgaradi.
    """

    queryset = Lesson.objects.select_related(
        "group", "room", "teacher__user", "center"
    )
    serializer_class = LessonSerializer

    # O'qituvchi davomat qo'yadi va mavzu yozadi, lekin faqat O'ZI dars
    # beradigan darslarda (teacher_field object-level tekshiruvi).
    write_roles = ("OWNER", "ADMIN")
    action_roles = {
        "attendance": ("OWNER", "ADMIN", "TEACHER"),
        "partial_update": ("OWNER", "ADMIN", "TEACHER"),
    }
    teacher_field = "teacher"

    def get_queryset(self):
        """Filtrlar: group, date_from, date_to, teacher, status."""
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get("group"):
            queryset = queryset.filter(group_id=params["group"])
        if params.get("teacher"):
            queryset = queryset.filter(teacher_id=params["teacher"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("date_from"):
            queryset = queryset.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(date__lte=params["date_to"])
        return queryset

    def _joriy_membership(self, lesson=None):
        """
        Amalni bajarayotgan a'zolik.

        Bir odam bir markazda bir nechta rolda bo'lishi mumkin. Agar dars
        aynan uning a'zoliklaridan biriga biriktirilgan bo'lsa, davomat
        o'sha a'zolik nomidan yoziladi - shunda `marked_by` to'g'ri bo'ladi
        (ACCOUNTANT emas, TEACHER).
        """
        memberships = getattr(self.request, "memberships", None) or []
        if lesson is not None:
            for membership in memberships:
                if membership.id == lesson.teacher_id:
                    return membership

        membership = getattr(self.request, "membership", None)
        if membership is None:
            raise DRFValidationError("Sizda bu markazda faol a'zolik yo'q.")
        return membership

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Darsni ko'chiradi: eskisi MOVED bo'ladi, yangisi PLANNED."""
        lesson = self.get_object()
        kirish = MoveLessonSerializer(data=request.data, context=self.get_serializer_context())
        kirish.is_valid(raise_exception=True)

        yangi = move_lesson(
            lesson,
            new_date=kirish.validated_data["date"],
            new_start=kirish.validated_data["start_time"],
            new_end=kirish.validated_data["end_time"],
            new_room=kirish.validated_data["room"],
            user=request.user,
            ip_address=client_ip(request),
        )
        return Response(
            {
                "moved_from": self.get_serializer(lesson).data,
                "lesson": self.get_serializer(yangi).data,
            },
            status=http_status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"])
    def attendance(self, request, pk=None):
        """Ommaviy davomat. POST dan keyin dars PLANNED -> HELD bo'ladi."""
        lesson = self.get_object()
        context = self.get_serializer_context()

        if request.method == "GET":
            queryset = Attendance.objects.filter(lesson=lesson).select_related("student")
            return Response(AttendanceSerializer(queryset, many=True, context=context).data)

        kirish = AttendanceBulkSerializer(data=request.data, context=context)
        kirish.is_valid(raise_exception=True)

        natija = mark_attendance(
            lesson,
            kirish.validated_data["items"],
            self._joriy_membership(lesson),
            ip_address=client_ip(request),
        )
        lesson.refresh_from_db()
        return Response(
            {
                "lesson_status": lesson.status,
                "attendances": AttendanceSerializer(natija, many=True, context=context).data,
            },
            status=http_status.HTTP_201_CREATED,
        )
