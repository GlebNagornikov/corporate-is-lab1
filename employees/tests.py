from rest_framework import status
from rest_framework.test import APITestCase

from .models import Department, Employee


class DepartmentApiTests(APITestCase):
    def test_create_and_list_departments(self):
        response = self.client.post(
            "/api/departments/",
            {"name": "Продажи", "description": "Отдел продаж"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get("/api/departments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_department_name_must_be_unique(self):
        Department.objects.create(name="Продажи")
        response = self.client.post(
            "/api/departments/", {"name": "Продажи"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_empty_department(self):
        department = Department.objects.create(name="Продажи")
        response = self.client.delete(f"/api/departments/{department.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Department.objects.filter(id=department.id).exists())

    def test_delete_department_with_employees_returns_409(self):
        department = Department.objects.create(name="Продажи")
        Employee.objects.create(
            full_name="Иванова Анна",
            position="Менеджер",
            hired_at="2026-09-15",
            department=department,
        )
        response = self.client.delete(f"/api/departments/{department.id}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Department.objects.filter(id=department.id).exists())


class EmployeeApiTests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Продажи")

    def test_create_employee(self):
        response = self.client.post(
            "/api/employees/",
            {
                "full_name": "Иванова Анна",
                "position": "Менеджер",
                "hired_at": "2026-09-15",
                "department": self.department.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Employee.objects.count(), 1)

    def test_department_is_required(self):
        response = self.client.post(
            "/api/employees/",
            {
                "full_name": "Иванова Анна",
                "position": "Менеджер",
                "hired_at": "2026-09-15",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_update_employee(self):
        employee = Employee.objects.create(
            full_name="Иванова Анна",
            position="Менеджер",
            hired_at="2026-09-15",
            department=self.department,
        )
        response = self.client.patch(
            f"/api/employees/{employee.id}/",
            {"position": "Ведущий менеджер"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.position, "Ведущий менеджер")

    def test_delete_employee(self):
        employee = Employee.objects.create(
            full_name="Иванова Анна",
            position="Менеджер",
            hired_at="2026-09-15",
            department=self.department,
        )
        response = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
