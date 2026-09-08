"""Loyihaga xos DRF xatoliklari va xato ishlovchisi."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler as drf_exception_handler


class MultipleCentersError(APIException):
    """
    Foydalanuvchi bir nechta markazda faol, lekin X-Center-Id yuborilmagan.

    Javob 400 bo'ladi va markazlar ro'yxati qaytadi.
    """

    status_code = 400
    default_detail = "Markazni tanlang."

    def __init__(self, centers):
        super().__init__(
            {
                "detail": (
                    "Siz bir nechta markazda faolsiz. "
                    "'X-Center-Id' sarlavhasida markazni ko'rsating."
                ),
                "centers": [
                    {"id": str(center.id), "name": center.name, "slug": center.slug}
                    for center in centers
                ],
            }
        )


def crm_exception_handler(exc, context):
    """
    services.py dagi Django ValidationError ni 400 ga aylantiradi.

    Bo'lmasa biznes qoidasi buzilganda 500 qaytardi.
    """
    if isinstance(exc, DjangoValidationError):
        from rest_framework.exceptions import ValidationError as DRFValidationError

        exc = DRFValidationError(as_serializer_error(exc))
    return drf_exception_handler(exc, context)
