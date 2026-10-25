from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    phone = models.CharField("Телефон", max_length=20, blank=True)
    employee = models.OneToOneField(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user",
        verbose_name="Карточка сотрудника",
    )
