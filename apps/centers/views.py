"""Filial API'si."""

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.centers.models import Branch
from apps.centers.serializers import BranchSerializer
from apps.common.utils import client_ip, diff_values, model_snapshot
from apps.common.viewsets import TenantViewSet

# Auditda kuzatiladigan maydonlar
BRANCH_AUDIT_FIELDS = ["name", "address", "phone", "status"]


class BranchViewSet(TenantViewSet):
    """Filiallar: ro'yxat, yaratish, o'zgartirish. O'chirish yo'q."""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance
        log_action(
            center=self.request.center,
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            instance=instance,
            new_values=model_snapshot(instance, BRANCH_AUDIT_FIELDS),
            ip_address=client_ip(self.request),
        )

    def perform_update(self, serializer):
        before = model_snapshot(serializer.instance, BRANCH_AUDIT_FIELDS)
        instance = serializer.save()
        after = model_snapshot(instance, BRANCH_AUDIT_FIELDS)
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
