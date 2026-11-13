from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from cart.services import add_to_cart
from catalog.models import Category, Product, ProductVariant
from orders.models import Order, Payment, PromoCode
from orders.services import OrderError, change_status, place_order

User = get_user_model()
CUSTOMER = {
    "full_name": "Покупатель",
    "phone": "8 (913) 000-00-00",
    "email": "b@example.com",
    "delivery_method": "pickup",
}


class OrderApiTests(APITestCase):
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
        cls.buyer = User.objects.create_user("buyer", password="pass12345")
        cls.other = User.objects.create_user("other", password="pass12345")
        cls.manager = User.objects.create_user("manager", password="pass12345", is_staff=True)
        cls.admin = User.objects.create_superuser("admin", password="pass12345")
        call_command("setup_groups", stdout=StringIO())
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))

    def buy(self, user):
        self.client.force_authenticate(user)
        response = self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 1})
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post("/api/orders/", CUSTOMER)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_anonymous_gets_401(self):
        for url in (
            "/api/orders/",
            "/api/cart/",
            "/api/employees/",
            "/api/departments/",
            "/api/auth/me/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response["WWW-Authenticate"].startswith("Bearer"))
        for url in ("/api/catalog/products/", "/api/catalog/categories/"):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post("/api/cart/merge/", {"items": []}).status_code, 401)

    def test_registration_validates_password_and_allows_jwt_login(self):
        url = "/api/auth/register/"
        payload = {"username": "new-buyer", "email": "new@example.com"}
        weak = self.client.post(url, {**payload, "password": "123"})
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.data)

        password = "Complex-pass-24"
        response = self.client.post(url, {**payload, "password": password, "is_staff": True})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        self.assertFalse(User.objects.get(pk=response.data["id"]).is_staff)
        token = self.client.post(
            "/api/auth/token/", {"username": payload["username"], "password": password}
        )
        self.assertEqual(token.status_code, 200, token.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200, me.data)
        self.assertEqual(me.data["username"], payload["username"])
        self.assertFalse(me.data["is_manager"])

    def test_me_reports_order_permission(self):
        self.client.force_authenticate(self.manager)
        self.assertTrue(self.client.get("/api/auth/me/").data["is_manager"])

    def test_staff_orders_endpoints_require_manager_role(self):
        order_id = self.buy(self.buyer)
        listing = "/api/manager/orders/"
        detail = f"{listing}{order_id}/"
        for user, expected in [(None, 401), (self.other, 403)]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(listing).status_code, expected)
            self.assertEqual(self.client.get(detail).status_code, expected)
            self.assertEqual(self.client.post(f"{detail}status/").status_code, expected)
        self.assertEqual(self.client.get(f"/api/orders/{order_id}/").status_code, 404)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(f"{listing}999999/").status_code, 404)

    def test_staff_cannot_delete_book_referenced_by_an_order_in_any_status(self):
        order_id = self.buy(self.buyer)
        self.client.force_authenticate(self.manager)
        detail = f"/api/manager/orders/{order_id}/"
        for status in Order.Status:
            with self.subTest(status=status):
                Order.objects.filter(pk=order_id).update(status=status)
                before = self.client.get(detail).data
                response = self.client.delete(f"/api/manager/catalog/{self.book.pk}/")
                self.assertEqual(response.status_code, 409, response.data)
                self.assertIn("Снимите её с продажи", response.data["detail"])
                self.assertTrue(Product.objects.filter(pk=self.book.pk).exists())
                self.assertEqual(self.client.get(detail).data, before)

    def test_staff_order_transition_shares_service_and_filter(self):
        order_id = self.buy(self.buyer)
        self.client.post(f"/api/orders/{order_id}/simulate-payment/", {"outcome": "success"})
        self.client.force_authenticate(self.manager)
        listing = "/api/manager/orders/"
        detail = f"{listing}{order_id}/"
        before = self.client.get(detail).data
        self.assertEqual(before["status"], "paid")
        self.assertEqual(set(before["allowed_transitions"]), {"confirmed", "cancelled"})
        result = self.client.post(f"{detail}status/", {"status": "delivered"})
        self.assertEqual(result.status_code, 400, result.data)
        after = self.client.get(detail).data
        self.assertEqual((after["status"], after["history"]), (before["status"], before["history"]))
        valid = self.client.post(f"{detail}status/", {"status": "confirmed"})
        self.assertEqual(valid.status_code, 200, valid.data)
        self.assertEqual(valid.data["history"][-1]["to_status"], "confirmed")
        filtered = self.client.get(listing, {"status": "confirmed"})
        self.assertEqual([row["id"] for row in filtered.data["results"]], [order_id])

    def test_merge_caps_quantity_and_skips_missing_or_inactive_products(self):
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.book, quantity=2)
        self.book.image = "products/book.jpg"
        self.book.save(update_fields=["image"])
        inactive = Product.objects.create(
            category=self.book.category,
            name="Снят",
            slug="hidden",
            sku="BK-2",
            price=1,
            stock=5,
            is_active=False,
        )
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/cart/merge/",
            {
                "items": [
                    {"product": self.book.pk, "quantity": 4},
                    {"product": inactive.pk, "quantity": 1},
                    {"product": inactive.pk + 1, "quantity": 1},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total"], "5000.00")
        (item,) = response.data["items"]
        self.assertEqual(item["quantity"], 5)
        self.assertEqual(item["slug"], self.book.slug)
        self.assertEqual(item["stock"], 5)
        self.assertEqual(item["image"], "http://testserver/media/products/book.jpg")
        self.assertEqual(cart.items.count(), 1)

    def test_merge_respects_variant_stock_and_price(self):
        variant = ProductVariant.objects.create(
            product=self.book, name="Коллекционное издание", sku="BK-C", stock=2, price=1500
        )
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/cart/merge/",
            {
                "items": [
                    {"product": self.book.pk, "quantity": 1},
                    {"product": self.book.pk, "variant": variant.pk, "quantity": 3},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        (item,) = response.data["items"]
        self.assertEqual(item["variant_id"], variant.pk)
        self.assertEqual(item["stock"], 2)
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["price"], "1500.00")
        self.assertIsNone(item["image"])

    def test_invalid_merge_does_not_apply_valid_lines(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/cart/merge/",
            {
                "items": [
                    {"product": self.book.pk, "quantity": 1},
                    {"product": self.book.pk, "quantity": 100},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)
        self.assertFalse(Cart.objects.filter(user=self.buyer).exists())

    def test_checkout_requires_delivery_method(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        response = self.client.post(
            "/api/orders/",
            {key: value for key, value in CUSTOMER.items() if key != "delivery_method"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("delivery_method", response.data)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Cart.objects.get(user=self.buyer).items.get().quantity, 1)

    def test_jwt_login_and_create_order(self):
        response = self.client.post(
            "/api/auth/token/", {"username": "buyer", "password": "pass12345"}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        cart = self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 2}).data
        self.assertEqual(cart["total"], "2000.00")
        response = self.client.post("/api/orders/", {**CUSTOMER, "delivery_method": "courier"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["detail"]), "Для доставки курьером укажите адрес.")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Cart.objects.get(user=self.buyer).items.get().quantity, 2)
        response = self.client.post(
            "/api/orders/",
            {**CUSTOMER, "delivery_method": "courier", "address": "ул. Каменская, 56"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "2500.00")
        self.assertEqual(response.data["phone"], "+79130000000")
        self.assertEqual(Order.objects.get().phone, "+79130000000")
        self.assertEqual(response.data["items"][0]["price"], "1000.00")
        self.assertEqual(response.data["allowed_transitions"], [])
        self.assertTrue(response.data["can_cancel"])
        self.assertIsNone(response.data["promo_code"])
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 3)
        self.assertFalse(Cart.objects.get(user=self.buyer).items.exists())

    def test_customer_sees_only_own_orders(self):
        own = self.buy(self.buyer)
        other = self.buy(self.other)
        self.client.force_authenticate(self.buyer)
        ids = [order["id"] for order in self.client.get("/api/orders/").data["results"]]
        self.assertEqual(ids, [own])
        self.assertEqual(self.client.get(f"/api/orders/{other}/").status_code, 404)

    def test_checkout_rejects_six_copies_in_one_line(self):
        Product.objects.filter(pk=self.book.pk).update(stock=8)
        self.client.force_authenticate(self.buyer)
        cart = self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 6})
        self.assertEqual(cart.status_code, 200, cart.data)
        response = self.client.post("/api/orders/", CUSTOMER)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("не больше 5 экземпляров", response.data["detail"])
        self.assertEqual(self.client.get("/api/cart/").data, cart.data)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 8)
        self.assertFalse(Order.objects.exists())

    def test_checkout_limit_combines_variants_and_accepts_five_at_server_prices(self):
        first = ProductVariant.objects.create(
            product=self.book, name="Вариант A", sku="BK-A", stock=4, price=1000
        )
        second = ProductVariant.objects.create(
            product=self.book, name="Вариант B", sku="BK-B", stock=4, price=1200
        )
        now = timezone.now()
        promo = PromoCode.objects.create(
            code="TEST10",
            discount_percent=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
            max_uses=1,
        )
        self.client.force_authenticate(self.buyer)
        cart = self.client.post(
            "/api/cart/merge/",
            {
                "items": [
                    {"product": self.book.pk, "variant": variant.pk, "quantity": 3}
                    for variant in (first, second)
                ],
            },
            format="json",
        )
        self.assertEqual(cart.status_code, 200, cart.data)
        payload = {**CUSTOMER, "promo_code": promo.code}
        response = self.client.post("/api/orders/", payload)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("В корзине 6", response.data["detail"])
        self.assertEqual(self.client.get("/api/cart/").data, cart.data)
        self.assertFalse(Order.objects.exists())
        for variant in (first, second):
            variant.refresh_from_db()
            self.assertEqual(variant.stock, 4)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 8)
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 0)

        updated = self.client.patch(
            f"/api/cart/items/{self.book.pk}/?variant={second.pk}", {"quantity": 2}
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        response = self.client.post(
            "/api/orders/",
            {**payload, "total": "0.01", "items": [{"price": "0.01", "quantity": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertCountEqual(
            [(item["variant"], item["quantity"], item["price"]) for item in response.data["items"]],
            [(first.pk, 3, "1000.00"), (second.pk, 2, "1200.00")],
        )
        self.assertEqual(response.data["subtotal"], "5400.00")
        self.assertEqual(response.data["discount"], "540.00")
        self.assertEqual(response.data["total"], "4860.00")
        self.assertEqual(self.client.get("/api/cart/").data["count"], 0)
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.stock, second.stock), (1, 2))

        cancelled = self.client.post(f"/api/orders/{response.data['id']}/cancel/")
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(cancelled.data["items"], response.data["items"])
        first.refresh_from_db()
        second.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual((first.stock, second.stock, self.book.stock), (4, 4, 8))

    def test_checkout_uses_fresh_stock_even_below_edition_limit(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 2})
        Product.objects.filter(pk=self.book.pk).update(stock=1)
        response = self.client.post("/api/orders/", CUSTOMER)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("осталось только 1 шт.", response.data["detail"])
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.get("/api/cart/").data["count"], 2)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 1)

    def test_checkout_rejects_stale_default_or_legacy_line_after_variant_creation(self):
        self.client.force_authenticate(self.buyer)
        cart = Cart.objects.create(user=self.buyer)
        add_to_cart(cart, self.book)
        line = cart.items.get()
        variant = ProductVariant.objects.create(
            product=self.book, name="Вариант", sku="BK-NEW", stock=4, price=1200
        )
        for variant_id in (line.variant_id, None):
            with self.subTest(variant_id=variant_id):
                CartItem.objects.filter(pk=line.pk).update(variant_id=variant_id)
                response = self.client.post("/api/orders/", CUSTOMER)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("выберите вариант книги", str(response.data))
                self.assertFalse(Order.objects.filter(user=self.buyer).exists())
                self.assertTrue(cart.items.filter(pk=line.pk).exists())
                variant.refresh_from_db()
                self.book.refresh_from_db()
                self.assertEqual((self.book.stock, variant.stock), (4, 4))

    def test_cart_rejects_amount_overflow_before_writing_and_can_read_existing_cart(self):
        self.client.force_authenticate(self.buyer)
        Product.objects.filter(pk=self.book.pk).update(price=Decimal("99999999.99"), stock=102)
        cart = Cart.objects.create(user=self.buyer)
        response = self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 101})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(cart.items.exists())

        line = CartItem.objects.create(cart=cart, product=self.book, quantity=102)
        response = self.client.get("/api/cart/")
        self.assertEqual(response.data["total"], "10199999998.98")
        response = self.client.patch(f"/api/cart/items/{self.book.pk}/", {"quantity": 101})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(CartItem.objects.filter(pk=line.pk).exists())

    def test_checkout_checks_shared_stock_for_legacy_and_default_lines(self):
        cart = Cart.objects.create(user=self.buyer)
        add_to_cart(cart, self.book, quantity=2)
        CartItem.objects.create(cart=cart, product=self.book, quantity=2)
        Product.objects.filter(pk=self.book.pk).update(stock=3)
        self.client.force_authenticate(self.buyer)
        response = self.client.post("/api/orders/", CUSTOMER)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("осталось только 3 шт.", response.data["detail"])
        self.assertFalse(Order.objects.exists())
        self.assertEqual(cart.count, 4)

    def test_customer_actions_require_the_owner_even_with_staff_read_permission(self):
        order_id = self.buy(self.buyer)
        url = f"/api/orders/{order_id}/"
        for user in (self.other, self.manager):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.post(f"{url}cancel/").status_code, 404)
                for payload in ({}, {"outcome": "success"}):
                    response = self.client.post(f"{url}simulate-payment/", payload)
                    self.assertEqual(response.status_code, 404, response.data)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.history.count(), 1)
        self.assertFalse(Payment.objects.exists())

    def test_only_manager_can_change_status(self):
        order_id = self.buy(self.buyer)
        url = f"/api/orders/{order_id}/status/"
        response = self.client.post(url, {"status": "confirmed"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("только менеджеры", str(response.data["detail"]))
        self.client.force_authenticate(self.manager)
        detail = self.client.get(f"/api/orders/{order_id}/").data
        self.assertEqual(detail["allowed_transitions"], ["cancelled"])
        self.assertFalse(detail["can_cancel"])
        self.assertEqual(self.client.post(url, {"status": "paid"}).status_code, 400)
        change_status(Order.objects.get(pk=order_id), "paid", by=self.buyer, payment_verified=True)
        self.assertEqual(len(self.client.get("/api/orders/").data["results"]), 1)
        response = self.client.post(url, {"status": "confirmed", "comment": "Позвонили"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Order.objects.get().status, "confirmed")
        self.assertEqual(response.data["allowed_transitions"], ["cancelled", "shipped"])
        self.assertEqual(len(response.data["history"]), 3)
        self.assertEqual(response.data["history"][-1]["changed_by"], str(self.manager))
        self.assertEqual(self.client.post(url, {"status": "new"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"status": "unknown"}).status_code, 400)

    def test_manager_cannot_skip_to_delivered_or_publish_an_event(self):
        order_id = self.buy(self.buyer)
        self.client.force_authenticate(self.manager)
        order = Order.objects.get(pk=order_id)
        history = list(order.history.values())
        stock = Product.objects.get(pk=self.book.pk).stock

        with self.captureOnCommitCallbacks() as callbacks:
            response = self.client.post(
                f"/api/manager/orders/{order_id}/status/", {"status": Order.Status.DELIVERED}
            )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertTrue(response.data["detail"])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(list(order.history.values()), history)
        self.assertEqual(Product.objects.get(pk=self.book.pk).stock, stock)
        self.assertEqual(callbacks, [])

    def test_manager_cancellation_requires_a_comment(self):
        order_id = self.buy(self.buyer)
        self.client.force_authenticate(self.manager)
        url = f"/api/orders/{order_id}/status/"
        for fields in ({}, {"comment": "  "}):
            with self.subTest(fields=fields):
                response = self.client.post(url, {"status": "cancelled", **fields})
                self.assertEqual(response.status_code, 400)
                self.assertIn("comment", response.data)
        self.assertEqual(Order.objects.get(pk=order_id).status, "new")
        response = self.client.post(url, {"status": "cancelled", "comment": "Причина отмены"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertEqual(response.data["history"][-1]["comment"], "Причина отмены")

    def test_employees_api_is_closed_for_customers(self):
        for user in (self.buyer, self.manager):
            self.client.force_authenticate(user)
            for url in ("/api/employees/", "/api/departments/"):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.head(url).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/employees/").status_code, 200)
        self.assertEqual(self.client.get("/api/departments/").status_code, 200)

    def test_jwt_refresh_and_bad_credentials(self):
        self.assertEqual(
            self.client.post(
                "/api/auth/token/", {"username": "buyer", "password": "wrong"}
            ).status_code,
            401,
        )
        tokens = self.client.post(
            "/api/auth/token/", {"username": "buyer", "password": "pass12345"}
        ).data
        response = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get("/api/orders/").status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['refresh']}")
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)

    def test_cart_get_update_delete_and_validation(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.get("/api/cart/")
        self.assertEqual(
            response.data,
            {"items": [], "count": 0, "total": "0.00", "promo_code": "", "promo_quote": None},
        )
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        url = f"/api/cart/items/{self.book.pk}/"
        response = self.client.patch(url, {"quantity": 3})
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["total"], "3000.00")
        self.assertEqual(self.client.patch(url, {"quantity": -1}).status_code, 400)
        self.assertEqual(self.client.delete(url).data["count"], 0)
        self.assertEqual(
            self.client.post(
                "/api/cart/items/", {"product": self.book.pk, "quantity": 0}
            ).status_code,
            400,
        )
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])
        self.assertEqual(
            self.client.post("/api/cart/items/", {"product": self.book.pk}).status_code, 400
        )
        self.assertEqual(self.client.patch(url, {"quantity": 1}).status_code, 400)

    def test_add_rejects_sold_out_book_and_variant(self):
        self.client.force_authenticate(self.buyer)
        self.book.stock = 0
        self.book.save(update_fields=["stock"])
        for with_variant in (False, True):
            with self.subTest(with_variant=with_variant):
                payload = {"product": self.book.pk}
                if with_variant:
                    variant = ProductVariant.objects.create(
                        product=self.book,
                        name="Склад",
                        sku="SOLD-OUT",
                        price=self.book.price,
                        stock=0,
                    )
                    payload["variant"] = variant.pk
                response = self.client.post("/api/cart/items/", payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("Книги больше нет в наличии.", response.data)
                self.assertEqual(self.client.get("/api/cart/").data["items"], [])

    def test_cart_is_private_and_zero_quantity_removes_item(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/cart/").data["count"], 0)
        self.client.force_authenticate(self.buyer)
        response = self.client.patch(f"/api/cart/items/{self.book.pk}/", {"quantity": 0})
        self.assertEqual(response.data["count"], 0)

    def test_zero_quantity_removes_unavailable_book_and_clears_promo(self):
        self.client.force_authenticate(self.buyer)
        cart = Cart.objects.create(user=self.buyer)
        add_to_cart(cart, self.book, quantity=2)
        cart.promo_code = "BOOK10"
        cart.save(update_fields=["promo_code"])
        variant_id = cart.items.get().variant_id
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])

        response = self.client.patch(
            f"/api/cart/items/{self.book.pk}/?variant={variant_id}", {"quantity": 0}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["promo_code"], "")

    def test_zero_quantity_removes_only_selected_inactive_variant(self):
        self.client.force_authenticate(self.buyer)
        cart = Cart.objects.create(user=self.buyer)
        first, second = [
            ProductVariant.objects.create(
                product=self.book, name=sku, sku=sku, price=self.book.price, stock=3
            )
            for sku in ("FIRST", "SECOND")
        ]
        add_to_cart(cart, self.book, quantity=2, variant=first)
        add_to_cart(cart, self.book, variant=second)
        first.is_active = False
        first.save(update_fields=["is_active"])

        url = f"/api/cart/items/{self.book.pk}/"
        self.assertEqual(self.client.patch(url, {"quantity": 0}).status_code, 200)
        self.assertEqual(cart.items.count(), 2)
        response = self.client.patch(f"{url}?variant={first.pk}", {"quantity": 0})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(cart.items.get().variant_id, second.pk)

    def test_cancel_old_orders_after_first_warehouse_variant_is_added(self):
        first_order_id = self.buy(self.buyer)
        second_order_id = self.buy(self.buyer)
        Order.objects.get(pk=second_order_id).items.update(variant=None)
        warehouse = ProductVariant.objects.create(
            product=self.book, name="Другой склад", sku="NEW-WAREHOUSE", price=1200, stock=3
        )

        for order_id in (first_order_id, second_order_id):
            url = f"/api/orders/{order_id}/cancel/"
            self.assertEqual(self.client.post(url).status_code, 200)
            self.assertEqual(self.client.post(url).status_code, 400)

        returned = self.book.variants.get(is_legacy_return=True)
        self.assertEqual(returned.stock, 2)
        self.assertFalse(returned.is_active)
        warehouse.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual((self.book.stock, warehouse.stock), (3, 3))

        self.client.force_authenticate(self.manager)
        url = f"/api/manager/catalog/{self.book.pk}/variants/{returned.pk}/"
        response = self.client.patch(url, {"is_active": True})
        self.assertEqual(response.status_code, 200, response.data)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)

    def test_customer_can_cancel_only_new_order(self):
        order_id = self.buy(self.buyer)
        response = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertFalse(response.data["can_cancel"])
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/cancel/").status_code, 400)
        order_id = self.buy(self.buyer)
        self.client.force_authenticate(self.manager)
        change_status(Order.objects.get(pk=order_id), "paid", by=self.buyer, payment_verified=True)
        self.client.post(f"/api/orders/{order_id}/status/", {"status": "confirmed"})
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/cancel/").status_code, 400)

    def test_orders_cannot_be_updated_or_deleted(self):
        order_id = self.buy(self.buyer)
        url = f"/api/orders/{order_id}/"
        self.assertEqual(self.client.patch(url, {"status": "delivered"}).status_code, 405)
        self.assertEqual(self.client.put(url, {}).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_manager_can_filter_orders_by_status(self):
        first = self.buy(self.buyer)
        second = self.buy(self.other)
        self.client.force_authenticate(self.manager)
        change_status(Order.objects.get(pk=first), "paid", by=self.buyer, payment_verified=True)
        self.client.post(f"/api/orders/{first}/status/", {"status": "confirmed"})
        response = self.client.get("/api/orders/", {"status": "new"})
        self.assertEqual([row["id"] for row in response.data["results"]], [second])

    def test_empty_cart_returns_400(self):
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post("/api/orders/", CUSTOMER).status_code, 400)
        self.client.get("/api/cart/")
        self.assertEqual(self.client.post("/api/orders/", CUSTOMER).status_code, 400)

    def test_checkout_ignores_server_controlled_fields(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        response = self.client.post(
            "/api/orders/",
            {
                **CUSTOMER,
                "status": "delivered",
                "price": "0.01",
                "subtotal": "0.01",
                "discount": "999.99",
                "total": "0.01",
                "items": [{"product": self.book.pk, "price": "0.01", "quantity": 5}],
                "user": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "new")
        self.assertEqual(response.data["total"], "1000.00")
        order = Order.objects.get()
        self.assertEqual(order.user, self.buyer)
        self.assertEqual(order.subtotal, Decimal("1000.00"))
        self.assertEqual(order.discount, Decimal("0.00"))
        self.assertEqual(order.items.get().price, Decimal("1000.00"))
        self.assertEqual(order.items.get().quantity, 1)

    def test_courier_address_rule_is_enforced_in_service(self):
        cart = Cart.objects.create(user=self.buyer)
        add_to_cart(cart, self.book)
        with self.assertRaisesMessage(OrderError, "укажите адрес"):
            place_order(
                user=self.buyer,
                cart=cart,
                **{**CUSTOMER, "delivery_method": "courier", "address": "   "},
            )
        self.assertFalse(Order.objects.exists())

    def test_employee_read_permission_does_not_grant_write(self):
        self.buyer.user_permissions.add(
            Permission.objects.get(content_type__app_label="employees", codename="view_employee")
        )
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get("/api/employees/").status_code, 200)
        self.assertEqual(self.client.post("/api/employees/", {}).status_code, 403)
        self.assertEqual(self.client.get("/api/departments/").status_code, 403)

    def test_cart_patch_quantity_is_limited_by_stock(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        response = self.client.patch(
            f"/api/cart/items/{self.book.pk}/", {"quantity": self.book.stock + 100}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["items"][0]["quantity"], self.book.stock)
        self.assertEqual(response.data["total"], "5000.00")
        self.assertEqual(Cart.objects.get(user=self.buyer).items.get().quantity, self.book.stock)

    def test_customer_cannot_cancel_someone_elses_order(self):
        order_id = self.buy(self.other)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Order.objects.get(pk=order_id).status, Order.Status.NEW)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 4)
        self.assertEqual(Order.objects.get(pk=order_id).history.count(), 1)

    def test_invalid_phone_returns_field_error_without_changing_cart_or_stock(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk, "quantity": 2})
        response = self.client.post("/api/orders/", {**CUSTOMER, "phone": "123"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)
        self.assertFalse(Order.objects.exists())
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        self.assertEqual(Cart.objects.get(user=self.buyer).items.get().quantity, 2)
