from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from cart.models import Cart
from cart.services import add_to_cart, set_cart_promo
from catalog.models import Category, Product
from orders.models import Order, PromoCode

from .test_api import CUSTOMER

User = get_user_model()
CHECK = "/api/promo/check/"
CART_PROMO = "/api/cart/promo/"
MANAGER_PROMOS = "/api/manager/promos/"


def promo_fields(code):
    now = timezone.now()
    return {
        "code": code,
        "discount_percent": 10,
        "minimum_subtotal": "1000.00",
        "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=1),
        "max_uses": 1,
    }


def make_book(category, sku):
    return Product.objects.create(
        category=category, name=sku, slug=sku, sku=sku, stock=10, price=Decimal("500.00")
    )


class PromoApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Книги", slug="books")
        cls.book = make_book(category, "edition")
        cls.buyer = User.objects.create_user("buyer")
        cls.manager = User.objects.create_user("manager")
        call_command("setup_groups", stdout=StringIO())
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))
        cls.promo = PromoCode.objects.create(**promo_fields("BOOK10"))

    def check_promo(self, subtotal):
        result = self.client.post(CHECK, {"code": " book10 ", "subtotal": subtotal})
        self.assertEqual(result.status_code, 200, result.data)
        return result.data

    def add(self, quantity):
        result = self.client.post(
            "/api/cart/items/", {"product": self.book.pk, "quantity": quantity}
        )
        self.assertEqual(result.status_code, 200, result.data)
        return result.data

    def select(self, code):
        return self.client.patch(CART_PROMO, {"promo_code": code})

    def assert_rejected_order(self, reason, **extra):
        cart = Cart.objects.get(user=self.buyer)
        stock = Product.objects.get(pk=self.book.pk).stock
        used_count = PromoCode.objects.get(pk=self.promo.pk).used_count
        items = list(cart.items.values())
        count = Order.objects.count()
        response = self.client.post("/api/orders/", {**CUSTOMER, **extra})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(reason, response.data["detail"])
        self.assertEqual(list(cart.items.values()), items)
        self.assertEqual(Cart.objects.get(pk=cart.pk).promo_code, cart.promo_code)
        self.assertEqual(Order.objects.count(), count)
        self.book.refresh_from_db()
        self.promo.refresh_from_db()
        self.assertEqual(self.book.stock, stock)
        self.assertEqual(self.promo.used_count, used_count)

    def test_quote_uses_db_for_buyer_and_does_not_consume_usage(self):
        self.assertEqual(self.check_promo("1000.00")["discount"], "100.00")
        self.assertEqual(self.client.patch(CART_PROMO, {"promo_code": "BOOK10"}).status_code, 401)
        self.client.force_authenticate(self.buyer)
        self.add(1)
        self.assertIn("от 1000.00", self.check_promo("99999.00")["reason"])
        self.assertEqual(self.select("BOOK10").status_code, 400)
        self.add(1)
        self.assertEqual(self.check_promo("0.00")["discount"], "100.00")
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.used_count, 0)

    def test_saved_code_recalculates_and_checkout_uses_it_when_omitted(self):
        self.client.force_authenticate(self.buyer)
        self.add(2)
        saved = self.select(" book10 ")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["promo_code"], "BOOK10")
        url = f"/api/cart/items/{self.book.pk}/"
        reduced = self.client.patch(url, {"quantity": 1})
        self.assertEqual(reduced.data["promo_code"], "BOOK10")
        self.assertEqual(reduced.data["promo_quote"]["total"], "500.00")
        self.assertIn("от 1000.00", reduced.data["promo_quote"]["reason"])
        self.assert_rejected_order("от 1000.00")
        self.assertEqual(self.add(1)["promo_quote"]["discount"], "100.00")
        response = self.client.post("/api/orders/", CUSTOMER)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "900.00")
        self.assertEqual(self.client.get("/api/cart/").data["promo_code"], "")
        self.add(2)
        self.assert_rejected_order("исчерпан", promo_code="BOOK10")
        self.assertEqual(self.promo.used_count, 1)

    def test_removing_last_line_clears_promo_from_saved_cart(self):
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.select("BOOK10").status_code, 400)
        empty = self.client.post(
            "/api/cart/merge/", {"items": [], "promo_code": "BOOK10"}, format="json"
        )
        self.assertEqual(empty.status_code, 200, empty.data)
        self.assertEqual(empty.data["promo_code"], "")
        url = f"/api/cart/items/{self.book.pk}/"
        for method in ("patch", "delete"):
            with self.subTest(method=method):
                self.add(2)
                self.assertEqual(self.select("BOOK10").status_code, 200)
                response = (
                    self.client.patch(url, {"quantity": 0})
                    if method == "patch"
                    else self.client.delete(url)
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["items"], [])
                self.assertEqual(response.data["promo_code"], "")
                self.assertIsNone(response.data["promo_quote"])
                self.assertEqual(Cart.objects.get(user=self.buyer).promo_code, "")

    def test_cart_merge_prefers_server_code_and_can_remove_it(self):
        self.client.force_authenticate(self.buyer)
        body = {
            "items": [{"product": self.book.pk, "quantity": 2}],
            "promo_code": "book10",
        }
        merged = self.client.post("/api/cart/merge/", body, format="json")
        self.assertEqual(merged.status_code, 200, merged.data)
        self.assertEqual(merged.data["promo_code"], "BOOK10")
        self.assertEqual(merged.data["promo_quote"]["discount"], "100.00")
        other = self.client.post(
            "/api/cart/merge/", {"items": [], "promo_code": "OTHER"}, format="json"
        )
        self.assertEqual(other.status_code, 200, other.data)
        self.assertEqual(other.data["promo_code"], "BOOK10")
        removed = self.select("")
        self.assertEqual(removed.status_code, 200, removed.data)
        self.assertEqual(removed.data["promo_code"], "")
        self.assertIsNone(removed.data["promo_quote"])

    def test_manager_permissions_and_deactivation(self):
        payload = promo_fields(" test10 ")
        disable = f"{MANAGER_PROMOS}{self.promo.pk}/deactivate/"
        self.assertEqual(self.client.get(MANAGER_PROMOS).status_code, 401)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get(MANAGER_PROMOS).status_code, 403)
        self.assertEqual(self.client.post(MANAGER_PROMOS, payload).status_code, 403)
        self.assertEqual(self.client.post(disable).status_code, 403)
        self.add(2)
        self.assertEqual(self.select("BOOK10").status_code, 200)

        self.client.force_authenticate(self.manager)
        created = self.client.post(MANAGER_PROMOS, {**payload, "used_count": 80})
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["code"], "TEST10")
        self.assertEqual(created.data["used_count"], 0)
        self.assertEqual(self.client.post(MANAGER_PROMOS, payload).status_code, 400)
        self.assertEqual(self.client.get(MANAGER_PROMOS).data["count"], 2)
        self.assertEqual(self.client.post(disable).status_code, 204)

        self.client.force_authenticate(self.buyer)
        self.assertIn("деактивирован", self.check_promo("1000.00")["reason"])
        self.assertEqual(self.select("BOOK10").status_code, 400)
        self.assert_rejected_order("деактивирован", promo_code="BOOK10")


class ConcurrentPromoTests(APITransactionTestCase):
    def test_only_one_order_can_redeem_the_last_use(self):
        category = Category.objects.create(name="Книги", slug="books")
        promo = PromoCode.objects.create(**promo_fields("LAST10"))
        carts = []
        for index in range(2):
            user = User.objects.create_user(f"buyer{index}")
            book = make_book(category, f"edition-{index}")
            cart = Cart.objects.create(user=user)
            add_to_cart(cart, book, 2)
            set_cart_promo(cart, promo.code)
            carts.append((cart, book))
        ready = Barrier(2, timeout=10)

        def buy(user):
            try:
                client = APIClient()
                client.force_authenticate(user)
                ready.wait()
                response = client.post("/api/orders/", CUSTOMER)
                return response.status_code, response.data
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(buy, [cart.user for cart, _ in carts]))
        self.assertEqual(sorted(status for status, _ in results), [201, 400], results)
        self.assertEqual(Order.objects.filter(promo_code=promo).count(), 1)
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)
        for (cart, book), (status, data) in zip(carts, results, strict=True):
            cart.refresh_from_db()
            book.refresh_from_db()
            if status == 400:
                self.assertIn("исчерпан", data["detail"])
                self.assertEqual(cart.promo_code, promo.code)
                self.assertEqual(cart.items.get().quantity, 2)
                self.assertEqual(book.stock, 10)
            else:
                self.assertFalse(cart.items.exists())
                self.assertEqual(book.stock, 8)
