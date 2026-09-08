"""Serializer bazalari."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class ValidatedModelSerializer(serializers.ModelSerializer):
    """
    Saqlashdan oldin model full_clean() ini chaqiradi.

    DRF ModelSerializer buni o'zi qilmaydi, natijada model clean() dagi
    biznes qoidalari API orqali chetlab o'tilardi. clean() hisoblab qo'ygan
    qiymatlar (masalan Group.end_date) ham shu yo'l bilan saqlanadi.
    """

    def _full_clean(self, instance):
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(serializers.as_serializer_error(exc))

    def create(self, validated_data):
        instance = self.Meta.model(**validated_data)
        self._full_clean(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        self._full_clean(instance)
        instance.save()
        return instance


class TenantModelSerializer(ValidatedModelSerializer):
    """
    FK qiymatlari so'rov markaziga tegishliligini tekshiradi.

    `tenant_fk_fields` da sanalgan har bir FK uchun obyektning `center` i
    request.center ga teng bo'lishi shart. Aks holda 400 va maydon nomi
    bilan aniq xato qaytadi (404 emas - bu yaratish/tahrirlash payti).
    """

    tenant_fk_fields = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        center = getattr(self.context.get("request"), "center", None)
        if center is None:
            return attrs

        errors = {}
        for field in self.tenant_fk_fields:
            value = attrs.get(field)
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            for item in items:
                if getattr(item, "center_id", None) != center.id:
                    errors[field] = "Bu obyekt boshqa markazga tegishli."
                    break
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
