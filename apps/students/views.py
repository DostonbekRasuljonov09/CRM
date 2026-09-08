"""O'quvchi API'si."""

from apps.common.viewsets import TenantViewSet
from apps.students.models import Student
from apps.students.serializers import StudentSerializer


class StudentViewSet(TenantViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
