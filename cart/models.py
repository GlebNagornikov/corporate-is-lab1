from django.conf import settings
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    """Корзина пользователя или гостя, чей cart_id хранится в сессии."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
        verbose_name="Покупатель",
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Изменена", auto_now=True)

    class Meta:
        verbose_name = "корзина"
        verbose_name_plural = "корзины"

    def __str__(self):
        return f"Корзина #{self.pk} ({self.user or 'гость'})"

    @property
    def total(self):
        return sum((item.total for item in self.items.all()), start=0)

    @property
    def count(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="one_line_per_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cart_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    @property
    def total(self):
        return self.product.price * self.quantity
