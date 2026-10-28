from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from orders.models import Order

User = get_user_model()


class CheckoutViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Книги", slug="books")
        cls.book = Product.objects.create(
            category=category,
            name="Чистый код",
            slug="clean-code",
            sku="BK-1",
            price=Decimal("1000"),
            stock=5,
        )
        cls.user = User.objects.create_user("buyer", password="pass12345", email="b@example.com")

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('orders:checkout')}")

    def test_full_purchase(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": 2})
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Покупатель",
                "phone": "+79130000000",
                "email": "b@example.com",
                "delivery_method": "courier",
                "address": "",
            },
        )
        self.assertFormError(
            response.context["form"], "address", "Для доставки курьером укажите адрес."
        )
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Покупатель",
                "phone": "+79130000000",
                "email": "b@example.com",
                "delivery_method": "pickup",
            },
        )
        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.total, Decimal("2000"))

    def test_customer_sees_only_own_orders(self):
        other = User.objects.create_user("other", password="pass12345")
        order = Order.objects.create(
            user=other,
            full_name="X",
            phone="1",
            email="x@example.com",
            subtotal=Decimal("1"),
            total=Decimal("1"),
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)
