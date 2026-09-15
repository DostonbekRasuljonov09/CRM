"""Foydalanuvchi va a'zolik serializerlari."""

from rest_framework import serializers

from apps.accounts.models import Membership, User
from apps.common.serializers import TenantModelSerializer
from apps.centers.models import Branch
from apps.centers.serializers import CenterShortSerializer


class MembershipSerializer(TenantModelSerializer):
    """A'zolik. center faqat o'qish uchun - u serverda o'rnatiladi.

    full_clean() ishlaydi: takroriy (user, center, role) 500 emas, 400.
    """

    tenant_fk_fields = ("branches",)

    branches = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Branch.objects.all(),
        required=False,
    )

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "center",
            "branches",
            "role",
            "status",
            "started_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "center", "created_at", "updated_at"]

    def validate_branches(self, value):
        """Filiallar shu markazga tegishli bo'lishi shart."""
        center = getattr(self.context.get("request"), "center", None)
        if center is None:
            return value
        begona = [branch.name for branch in value if branch.center_id != center.id]
        if begona:
            raise serializers.ValidationError(
                "Bu filiallar tanlangan markazga tegishli emas: " + ", ".join(begona)
            )
        return value


class BranchShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "status"]
        read_only_fields = fields


class MyMembershipSerializer(serializers.ModelSerializer):
    """Bitta a'zolik - /api/me/ javobi uchun."""

    center = CenterShortSerializer(read_only=True)
    branches = BranchShortSerializer(many=True, read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "center", "branches", "role", "status", "started_at"]
        read_only_fields = fields


class MeSerializer(serializers.ModelSerializer):
    """Foydalanuvchi va uning barcha a'zoliklari."""

    memberships = MyMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "date_joined",
            "memberships",
        ]
        read_only_fields = fields
