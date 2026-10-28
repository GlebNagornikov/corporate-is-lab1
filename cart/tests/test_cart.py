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

    def test_login_skips_inactive_product_and_preserves_available_items(self):
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 2})
        unavailable = Product.objects.create(
            category=self.product.category,
            name="Unavailable",
            slug="unavailable",
            sku="UNAVAILABLE",
            price=Decimal(100),
            stock=2,
        )
        self.client.post(reverse("cart:add", args=[unavailable.pk]), {"quantity": 1})
        Product.objects.filter(pk=unavailable.pk).update(is_active=False)
        response = self.client.post(
            reverse("login"), {"username": "buyer", "password": "pass12345"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get().product_id, self.product.pk)
        self.assertEqual(cart.items.get().quantity, 2)
        self.assertNotIn("cart_id", self.client.session)
        self.assertFalse(Cart.objects.filter(user__isnull=True).exists())
        from django.contrib.messages import get_messages

        self.assertTrue(any("Unavailable" in str(m) for m in get_messages(response.wsgi_request)))

    def test_login_skips_product_that_went_out_of_stock(self):
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 2})
        Product.objects.filter(pk=self.product.pk).update(stock=0)
        response = self.client.post(
            reverse("login"), {"username": "buyer", "password": "pass12345"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Cart.objects.get(user=self.user).items.exists())
        self.assertFalse(Cart.objects.filter(user__isnull=True).exists())

    def test_add_rejects_external_and_unsafe_redirects(self):
        for next_url in ["https://example.org/", "//example.org/", "javascript:alert(1)"]:
            with self.subTest(next_url=next_url):
                response = self.client.post(
                    reverse("cart:add", args=[self.product.pk]),
                    {"quantity": 1, "next": next_url},
                )
                self.assertRedirects(response, reverse("cart:detail"))

    def test_add_keeps_safe_local_redirect(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.pk]),
            {"quantity": 1, "next": self.product.get_absolute_url()},
        )
        self.assertRedirects(response, self.product.get_absolute_url())
