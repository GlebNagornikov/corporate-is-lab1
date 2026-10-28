from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product

User = get_user_model()


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Книги", slug="books")
        cls.product = Product.objects.create(
            category=category,
            name="Книга",
            slug="book",
            sku="BK-1",
            price=Decimal("1000"),
            stock=5,
        )
        cls.user = User.objects.create_user("buyer", password="pass12345")

    def test_quantity_is_limited_by_stock(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(add_to_cart(cart, self.product, 3), 3)
        self.assertEqual(add_to_cart(cart, self.product, 10), 5)

    def test_guest_cart_is_merged_on_login(self):
        add_url = reverse("cart:add", args=[self.product.pk])
        self.client.post(add_url, {"quantity": 2})
        user_cart = Cart.objects.create(user=self.user)
        add_to_cart(user_cart, self.product, 1)
        self.client.post(reverse("login"), {"username": "buyer", "password": "pass12345"})
        self.assertEqual(user_cart.items.get().quantity, 3)
        self.assertFalse(Cart.objects.filter(user__isnull=True).exists())
