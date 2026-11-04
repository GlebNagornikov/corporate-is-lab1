from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class PromoCode(models.Model):
    code = models.CharField("Код", max_length=30, unique=True)
    discount_percent = models.PositiveSmallIntegerField(
        "Скидка, %", validators=[MinValueValidator(1), MaxValueValidator(90)]
    )
    valid_from = models.DateTimeField("Действует с")
    valid_until = models.DateTimeField("Действует по")
    max_uses = models.PositiveIntegerField(
        "Лимит использований", null=True, blank=True, help_text="Пусто — без ограничений"
    )
    used_count = models.PositiveIntegerField("Использован, раз", default=0, editable=False)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "промокод"
        verbose_name_plural = "промокоды"

    def __str__(self):
        return f"{self.code} (−{self.discount_percent}%)"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid_now(self):
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now <= self.valid_until
            and (self.max_uses is None or self.used_count < self.max_uses)
        )


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        SHIPPED = "shipped", "Передан в доставку"
        DELIVERED = "delivered", "Доставлен"
        CANCELLED = "cancelled", "Отменён"

    class Delivery(models.TextChoices):
        PICKUP = "pickup", "Самовывоз"
        COURIER = "courier", "Курьер"

    TRANSITIONS = {
        Status.NEW: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.DELIVERED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Покупатель",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    full_name = models.CharField("Получатель", max_length=200)
    phone = models.CharField("Телефон", max_length=20)
    email = models.EmailField("Email")
    delivery_method = models.CharField(
        "Доставка", max_length=20, choices=Delivery.choices, default=Delivery.PICKUP
    )
    address = models.CharField("Адрес доставки", max_length=300, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Промокод",
    )
    subtotal = models.DecimalField("Сумма товаров", max_digits=12, decimal_places=2)
    discount = models.DecimalField("Скидка", max_digits=12, decimal_places=2, default=0)
    delivery_cost = models.DecimalField("Доставка", max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField("Итого", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        constraints = [
            models.CheckConstraint(
                condition=~Q(delivery_method="courier") | ~Q(address=""),
                name="courier_order_has_address",
            ),
        ]

    def __str__(self):
        return f"Заказ №{self.pk}"

    def get_absolute_url(self):
        return reverse("orders:detail", args=[self.pk])

    def can_change_to(self, status):
        return status in self.TRANSITIONS[self.status]

    @property
    def can_be_cancelled_by_customer(self):
        return self.status == self.Status.NEW


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    product_name = models.CharField("Товар", max_length=200)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество")

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def total(self):
        return self.price * self.quantity


class OrderStatusLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField("Был", max_length=20, choices=Order.Status.choices, blank=True)
    to_status = models.CharField("Стал", max_length=20, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name="Кто изменил",
    )
    comment = models.CharField("Комментарий", max_length=300, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "смена статуса"
        verbose_name_plural = "история статусов"

    def __str__(self):
        return f"{self.order}: {self.from_status or '—'} → {self.to_status}"
