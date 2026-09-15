"""Serializer bazalari."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers


class ValidatedModelSerializer(serializers.ModelSerializer):
    """
    Saqlashdan oldin model full_clean() ini chaqiradi.

    DRF ModelSerializer buni o'zi qilmaydi. Natijada model clean() dagi
    biznes qoidalari API orqali chetlab o'tilardi va `unique_together`
    buzilganda baza IntegrityError (500) bilan yiqilardi - `center`
    read_only bo'lgani uchun DRF unique validatorini qo'shmaydi.
    clean() hisoblab qo'ygan qiymatlar (Group.end_date) ham shu yo'l bilan saqlanadi.
    """

    def _full_clean(self, instance, exclude=None):
        try:
            instance.full_clean(exclude=exclude)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(serializers.as_serializer_error(exc))

    def _pop_m2m(self, validated_data):
        """M2M maydonlarni ajratadi - ular obyekt saqlangandan keyin o'rnatiladi."""
        m2m = {}
        for name, field in self.fields.items():
            if isinstance(field, serializers.ManyRelatedField) and name in validated_data:
                m2m[name] = validated_data.pop(name)
        return m2m

    @transaction.atomic
    def create(self, validated_data):
        m2m = self._pop_m2m(validated_data)
        instance = self.Meta.model(**validated_data)
        self._full_clean(instance)
        instance.save()
        for name, value in m2m.items():
            getattr(instance, name).set(value)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        m2m = self._pop_m2m(validated_data)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        self._full_clean(instance)
        instance.save()
        for name, value in m2m.items():
            getattr(instance, name).set(value)
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
