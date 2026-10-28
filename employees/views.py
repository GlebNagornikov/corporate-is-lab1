import logging

from rest_framework import viewsets

from .models import Department, Employee
from .permissions import StrictDjangoModelPermissions
from .serializers import DepartmentSerializer, EmployeeSerializer

# Create your views here.

logger = logging.getLogger(__name__)


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("department").order_by("full_name")
    serializer_class = EmployeeSerializer
    permission_classes = [StrictDjangoModelPermissions]

    def perform_create(self, serializer):
        employee = serializer.save()
        logger.info(
            "Создан сотрудник %s (id=%s), пользователь: %s",
            employee.full_name,
            employee.id,
            self.request.user,
        )

    def perform_destroy(self, instance):
        logger.warning(
            "Удалён сотрудник %s (id=%s), пользователь: %s",
            instance.full_name,
            instance.id,
            self.request.user,
        )
        instance.delete()


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [StrictDjangoModelPermissions]
