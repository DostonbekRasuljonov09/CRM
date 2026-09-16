"""Tenant filtri bilan ishlaydigan bazaviy viewsetlar."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import HasCenterRole, IsCenterMember
from apps.common.tenant import resolve_center

BASE_PERMISSIONS = [IsAuthenticated, IsCenterMember, HasCenterRole]


class CenterMixin:
    """
    request.center, request.memberships va request.membership ni o'rnatadi.

    `memberships` - shu markazdagi BARCHA faol a'zoliklar (bir odam bir
    markazda bir nechta rolda bo'lishi mumkin). `membership` - eng kuchli
    rolli a'zolik, audit va standart qiymatlar uchun.
    """

    def initial(self, request, *args, **kwargs):
        # Avval foydalanuvchini aniqlaymiz, keyin markaz va a'zoliklarni
        self.perform_authentication(request)
        request.center = None
        request.memberships = []
        request.membership = None
        if request.user and request.user.is_authenticated:
            request.center, request.memberships = resolve_center(request)
            request.membership = request.memberships[0]
        super().initial(request, *args, **kwargs)


class TenantQuerySetMixin:
    """
    Har doim faqat o'z markazining ma'lumotlarini ko'rsatadi.

    Begona markaz obyekti so'ralsa 404 qaytadi (403 emas) - chunki
    get_queryset() filtri uni umuman ko'rmaydi.
    """

    def get_queryset(self):
        return super().get_queryset().filter(center=self.request.center)

    def perform_create(self, serializer):
        # Mijoz yuborgan center qiymati e'tiborsiz qoldiriladi
        serializer.save(center=self.request.center)


class TenantViewSet(CenterMixin, TenantQuerySetMixin, viewsets.ModelViewSet):
    """To'liq CRUD (DELETE'siz): o'chirish o'rniga status o'zgartiriladi."""

    permission_classes = BASE_PERMISSIONS
    http_method_names = ["get", "post", "patch", "head", "options"]


class TenantReadUpdateViewSet(
    CenterMixin,
    TenantQuerySetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Yaratish yo'q - obyekt boshqa yo'l bilan paydo bo'ladi (masalan Lesson
    generatsiya orqali). POST faqat @action lar uchun ochiq, ro'yxatga
    POST qilinsa 405 qaytadi.
    """

    permission_classes = BASE_PERMISSIONS
    http_method_names = ["get", "post", "patch", "head", "options"]
