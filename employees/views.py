from django.shortcuts import render
from rest_framework import viewsets
from .models import Employee, Department
from .serializers import EmployeeSerializer, DepartmentSerializer
import logging

# Create your views here.

logger = logging.getLogger(__name__)

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("department")
    serializer_class = EmployeeSerializer

    def perform_create(self, serializer):
        employee = serializer.save()
        logger.info("Создан сотрудник %s (id=%s), пользователь: %s",
                    employee.full_name, employee.id, self.request.user)

    def perform_destroy(self, instance):
        logger.warning("Удалён сотрудник %s (id=%s), пользователь: %s",
                       instance.full_name, instance.id, self.request.user)
        instance.delete()


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer