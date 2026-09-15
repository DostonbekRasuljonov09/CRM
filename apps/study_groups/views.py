"""Guruh API'si."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.viewsets import TenantViewSet
from apps.study_groups.models import Group
from apps.study_groups.serializers import (
    EnrollmentCreateSerializer,
    GroupScheduleSerializer,
    GroupSerializer,
    GroupStudentSerializer,
    LeaveSerializer,
)
from apps.study_groups.services import (
    activate_group,
    add_student,
    apply_schedule_change,
    cancel_group,
    leave_group,
    sync_teacher,
)

# URL ichidagi UUID
UUID_RE = "[0-9a-fA-F-]{36}"


class GroupViewSet(TenantViewSet):
    """Guruhlar va ularning jadvali / o'quvchilari."""

    queryset = Group.objects.select_related("course", "branch", "teacher__user")
    serializer_class = GroupSerializer

    def perform_update(self, serializer):
        eski_teacher_id = serializer.instance.teacher_id
        # Guruhni saqlash va darslarni yangilash bitta tranzaksiyada:
        # ziddiyat chiqsa o'qituvchi ham almashmasligi kerak
        with transaction.atomic():
            group = serializer.save()
            if group.teacher_id != eski_teacher_id:
                sync_teacher(group)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Guruhni faollashtiradi va darslarni generatsiya qiladi."""
        group = self.get_object()
        lessons = activate_group(group)
        return Response(
            {
                "group": self.get_serializer(group).data,
                "lessons_created": len(lessons),
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Guruhni bekor qiladi va kelajakdagi darslarni ham CANCELLED qiladi."""
        group = self.get_object()
        bekor_qilingan = cancel_group(group)
        return Response(
            {
                "group": self.get_serializer(group).data,
                "lessons_cancelled": bekor_qilingan,
            }
        )

    @action(detail=True, methods=["get", "post"], url_path="schedules")
    def schedules(self, request, pk=None):
        """Guruh jadvali. Yangi jadval qo'shilsa darslar qayta yaratiladi."""
        group = self.get_object()
        context = self.get_serializer_context()

        if request.method == "GET":
            queryset = group.schedules.select_related("room")
            return Response(
                GroupScheduleSerializer(queryset, many=True, context=context).data
            )

        serializer = GroupScheduleSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(center=request.center, group=group)
            apply_schedule_change(group)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=f"schedules/(?P<schedule_id>{UUID_RE})",
    )
    def schedule_detail(self, request, pk=None, schedule_id=None):
        """Jadval qatorini tahrirlash - darslar qayta yaratiladi."""
        group = self.get_object()
        schedule = get_object_or_404(group.schedules, pk=schedule_id)
        serializer = GroupScheduleSerializer(
            schedule, data=request.data, partial=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            apply_schedule_change(group)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"], url_path="students")
    def students(self, request, pk=None):
        """Guruh o'quvchilari. Limitdan oshsa ogohlantirish qaytadi."""
        group = self.get_object()
        context = self.get_serializer_context()

        if request.method == "GET":
            queryset = group.enrollments.select_related("student")
            return Response(
                GroupStudentSerializer(queryset, many=True, context=context).data
            )

        kirish = EnrollmentCreateSerializer(data=request.data, context=context)
        kirish.is_valid(raise_exception=True)
        enrollment, warning = add_student(
            group,
            kirish.validated_data["student"],
            kirish.validated_data.get("joined_at"),
        )
        data = GroupStudentSerializer(enrollment, context=context).data
        if warning:
            data["warning"] = warning
        return Response(data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path=f"students/(?P<enrollment_id>{UUID_RE})/leave",
    )
    def student_leave(self, request, pk=None, enrollment_id=None):
        """O'quvchini guruhdan chiqaradi (o'chirmaydi - status LEFT)."""
        group = self.get_object()
        enrollment = get_object_or_404(group.enrollments, pk=enrollment_id)

        kirish = LeaveSerializer(data=request.data)
        kirish.is_valid(raise_exception=True)
        leave_group(enrollment, kirish.validated_data.get("left_at"))
        return Response(
            GroupStudentSerializer(enrollment, context=self.get_serializer_context()).data
        )
