from django.contrib.auth.models import AbstractUser
from django.db import models


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


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField("Название", max_length=60)
    city = models.CharField("Город", max_length=80)
    street = models.CharField("Улица", max_length=100)
    house = models.CharField("Дом", max_length=20)
    apartment = models.CharField("Квартира", max_length=20, blank=True)
    comment = models.CharField("Комментарий курьеру", max_length=100, blank=True)
    is_primary = models.BooleanField("Основной", default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(is_primary=True), name="one_primary_address"
            )
        ]
        ordering = ["-is_primary", "pk"]

    def __str__(self):
        return f"{self.label}: {self.snapshot}"

    @property
    def snapshot(self):
        return ", ".join(
            filter(None, [self.city, self.street, self.house, self.apartment, self.comment])
        )
