from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Department, Employee


class DepartmentDeletionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="Продажи")
        cls.empty_department = Department.objects.create(name="Новый отдел")
        cls.employee = Employee.objects.create(
            full_name="Иван Иванов",
            position="Менеджер",
            hired_at=date(2026, 9, 1),
            department=cls.department,
        )
        cls.operator = get_user_model().objects.create_user("operator")
        cls.operator.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="employees", codename="delete_department"
            )
        )
        cls.reader = get_user_model().objects.create_user("reader")
        cls.reader.user_permissions.add(
            Permission.objects.get(content_type__app_label="employees", codename="view_department")
        )

    def test_nonempty_department_returns_conflict_and_preserves_data(self):
        self.client.force_authenticate(self.operator)

        response = self.client.delete(reverse("department-detail", args=[self.department.pk]))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(), {"detail": "Нельзя удалить отдел, пока в нём есть сотрудники."}
        )
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.department_id, self.department.pk)

    def test_empty_department_can_be_deleted(self):
        self.client.force_authenticate(self.operator)

        response = self.client.delete(reverse("department-detail", args=[self.empty_department.pk]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Department.objects.filter(pk=self.empty_department.pk).exists())

    def test_view_permission_does_not_allow_deletion(self):
        self.client.force_authenticate(self.reader)

        for department in (self.department, self.empty_department):
            with self.subTest(department=department.pk):
                response = self.client.delete(reverse("department-detail", args=[department.pk]))
                self.assertEqual(response.status_code, 403)
                self.assertTrue(Department.objects.filter(pk=department.pk).exists())

    def test_anonymous_cannot_delete_department(self):
        response = self.client.delete(reverse("department-detail", args=[self.empty_department.pk]))

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Department.objects.filter(pk=self.empty_department.pk).exists())

    def test_missing_department_returns_not_found(self):
        self.client.force_authenticate(self.operator)
        missing_pk = self.empty_department.pk
        self.empty_department.delete()

        response = self.client.delete(reverse("department-detail", args=[missing_pk]))

        self.assertEqual(response.status_code, 404)
