from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Address
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

    def test_saved_address_prefills_single_editable_field_and_preserves_edits(self):
        primary = Address.objects.create(
            user=self.user,
            label="Дом",
            city="Москва",
            street="Мира",
            house="1",
            is_primary=True,
        )
        second = Address.objects.create(
            user=self.user, label="Работа", city="Москва", street="Садовая", house="3"
        )
        other = User.objects.create_user("address-other")
        foreign = Address.objects.create(
            user=other,
            label="Чужой",
            city="Секретный город",
            street="Улица",
            house="2",
        )
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": 1})
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.context["form"]["address"].value(), primary.snapshot)
        self.assertContains(response, 'name="address"', count=1)
        self.assertContains(response, 'aria-label="Сохранённые адреса"')
        self.assertNotContains(response, "Подставить сохранённый адрес")
        self.assertContains(
            response,
            f'value="{second.snapshot}"',
        )
        self.assertContains(response, f"{second.label} — {second.snapshot}")
        self.assertNotContains(response, 'name="address_book"')
        self.assertNotContains(response, foreign.snapshot)
        data = {
            "full_name": "Покупатель",
            "phone": "123",
            "email": "b@example.com",
            "delivery_method": "courier",
            "address": "Москва, Новый адрес, 2",
        }
        response = self.client.post(reverse("orders:checkout"), data)
        self.assertEqual(response.context["form"]["address"].value(), data["address"])
        response = self.client.post(reverse("orders:checkout"), {**data, "phone": "+79130000000"})
        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.address, data["address"])

    def test_full_purchase(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": 2})
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Покупатель",
                "phone": "8 (913) 000-00-00",
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
                "phone": "8 (913) 000-00-00",
                "email": "b@example.com",
                "delivery_method": "pickup",
            },
        )
        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.total, Decimal("2000"))
        self.assertEqual(order.phone, "+79130000000")

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

    def test_invalid_phone_is_shown_under_field_and_preserves_cart(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": 2})
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Покупатель",
                "phone": "123",
                "email": "b@example.com",
                "delivery_method": "pickup",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "phone",
            "Введите российский номер телефона, например +7 913 123-45-67.",
        )
        self.assertFalse(Order.objects.exists())
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(list(response.context["items"])[0].quantity, 2)
