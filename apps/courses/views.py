"""Kurs, xona va bayram API'si."""

from apps.common.viewsets import TenantViewSet
from apps.courses.models import Course, Holiday, Room
from apps.courses.serializers import CourseSerializer, HolidaySerializer, RoomSerializer


class CourseViewSet(TenantViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class RoomViewSet(TenantViewSet):
    queryset = Room.objects.select_related("branch")
    serializer_class = RoomSerializer


class HolidayViewSet(TenantViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
