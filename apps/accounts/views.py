"""Foydalanuvchi va a'zolik API'si."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.models import Membership, User
from apps.accounts.serializers import MeSerializer, MembershipSerializer
from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.common.utils import client_ip, diff_values, model_snapshot
from apps.common.viewsets import TenantViewSet

# Auditda kuzatiladigan maydonlar
MEMBERSHIP_AUDIT_FIELDS = ["role", "status", "started_at"]


class ThrottledLoginView(TokenObtainPairView):
    """Login. Parolni brute-force qilishga qarshi tezlik cheklovi bilan."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class MeView(APIView):
    """Joriy foydalanuvchi va uning barcha a'zoliklari. X-Center-Id kerak emas."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = (
            User.objects.filter(pk=request.user.pk)
            .prefetch_related("memberships__center", "memberships__branches")
            .first()
        )
        return Response(MeSerializer(user).data)


class MembershipViewSet(TenantViewSet):
    """
    Xodimlar (a'zoliklar): ro'yxat, yaratish, o'zgartirish. O'chirish yo'q.

    Faqat OWNER va ADMIN kira oladi - aks holda o'qituvchi o'zini OWNER
    qilib qo'yishi mumkin bo'lardi.
    """

    queryset = Membership.objects.select_related("user", "center").prefetch_related("branches")
    serializer_class = MembershipSerializer

    read_roles = ("OWNER", "ADMIN")
    write_roles = ("OWNER", "ADMIN")

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance
        log_action(
            center=self.request.center,
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            instance=instance,
            new_values=model_snapshot(instance, MEMBERSHIP_AUDIT_FIELDS),
            ip_address=client_ip(self.request),
        )

    def perform_update(self, serializer):
        # Hech kim o'z rolini yoki holatini o'zgartira olmaydi
        if serializer.instance.user_id == self.request.user.id:
            taqiqlangan = {"role", "status"} & set(serializer.validated_data)
            if taqiqlangan:
                raise PermissionDenied(
                    "O'zingizning rolingiz yoki holatingizni o'zgartira olmaysiz."
                )
        before = model_snapshot(serializer.instance, MEMBERSHIP_AUDIT_FIELDS)
        instance = serializer.save()
        after = model_snapshot(instance, MEMBERSHIP_AUDIT_FIELDS)
        old_values, new_values = diff_values(before, after)
        if new_values:
            log_action(
                center=self.request.center,
                user=self.request.user,
                action=AuditLog.Action.UPDATE,
                instance=instance,
                old_values=old_values,
                new_values=new_values,
                ip_address=client_ip(self.request),
            )
