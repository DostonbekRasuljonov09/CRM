"""Admin uchun umumiy yordamchilar."""

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.common.utils import client_ip, diff_values, model_snapshot


class AuditedAdminMixin:
    """Admin orqali qilingan yaratish/o'zgartirishni audit jurnaliga yozadi."""

    audit_fields = []

    def get_audit_center(self, obj):
        """Yozuv qaysi markazga tegishli. Center uchun - o'zi."""
        return getattr(obj, "center", obj)

    def save_model(self, request, obj, form, change):
        before = None
        if change and obj.pk:
            eski = self.model.objects.filter(pk=obj.pk).first()
            if eski is not None:
                before = model_snapshot(eski, self.audit_fields)

        super().save_model(request, obj, form, change)

        if change:
            after = model_snapshot(obj, self.audit_fields)
            old_values, new_values = diff_values(before or {}, after)
            if not new_values:
                return
            log_action(
                center=self.get_audit_center(obj),
                user=request.user,
                action=AuditLog.Action.UPDATE,
                instance=obj,
                old_values=old_values,
                new_values=new_values,
                ip_address=client_ip(request),
            )
        else:
            log_action(
                center=self.get_audit_center(obj),
                user=request.user,
                action=AuditLog.Action.CREATE,
                instance=obj,
                new_values=model_snapshot(obj, self.audit_fields),
                ip_address=client_ip(request),
            )
