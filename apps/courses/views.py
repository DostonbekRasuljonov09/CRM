"""Kurs, xona va bayram API'si."""

from apps.common.viewsets import TenantViewSet
from apps.lessons.services import apply_holiday, regenerate_for_date
from apps.courses.models import Course, Holiday, Room
from apps.courses.serializers import CourseSerializer, HolidaySerializer, RoomSerializer


class CourseViewSet(TenantViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class RoomViewSet(TenantViewSet):
    queryset = Room.objects.select_related("branch")
    serializer_class = RoomSerializer


class HolidayViewSet(TenantViewSet):
    """
    Bayram kunlari.

    Bayram qo'shilganda shu sanadagi kelajakdagi darslar olib tashlanadi -
    aks holda faol guruhlarda bayram kuniga dars qolib ketardi.
    """

    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        apply_holiday(serializer.instance)

    def perform_update(self, serializer):
        eski_sana = serializer.instance.date
        holiday = serializer.save()
        if eski_sana != holiday.date:
            # Bo'shab qolgan sanaga darslar qaytadi
            regenerate_for_date(holiday.center, eski_sana)
        apply_holiday(holiday)
