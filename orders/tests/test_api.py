from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from rest_framework.test import APITestCase

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product
from orders.models import Order
from orders.services import OrderError, place_order

User = get_user_model()
CUSTOMER = {
    "full_name": "Покупатель",
    "phone": "+7913",
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
        for url in ("/api/orders/", "/api/cart/", "/api/employees/", "/api/departments/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response["WWW-Authenticate"].startswith("Bearer"))
        for url in ("/api/catalog/products/", "/api/catalog/categories/"):
            self.assertEqual(self.client.get(url).status_code, 200)

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
        self.assertEqual(response.data["items"][0]["price"], "1000.00")
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

    def test_only_manager_can_change_status(self):
        order_id = self.buy(self.buyer)
        url = f"/api/orders/{order_id}/status/"
        response = self.client.post(url, {"status": "confirmed"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("только менеджеры", str(response.data["detail"]))
        self.client.force_authenticate(self.manager)
        self.assertEqual(len(self.client.get("/api/orders/").data["results"]), 1)
        response = self.client.post(url, {"status": "confirmed", "comment": "Позвонили"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Order.objects.get().status, "confirmed")
        self.assertEqual(len(response.data["history"]), 2)
        self.assertEqual(response.data["history"][-1]["changed_by"], str(self.manager))
        self.assertEqual(self.client.post(url, {"status": "new"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"status": "unknown"}).status_code, 400)

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
        self.assertEqual(response.data, {"items": [], "count": 0, "total": "0.00"})
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

    def test_cart_is_private_and_zero_quantity_removes_item(self):
        self.client.force_authenticate(self.buyer)
        self.client.post("/api/cart/items/", {"product": self.book.pk})
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/cart/").data["count"], 0)
        self.client.force_authenticate(self.buyer)
        response = self.client.patch(f"/api/cart/items/{self.book.pk}/", {"quantity": 0})
        self.assertEqual(response.data["count"], 0)

    def test_customer_can_cancel_only_new_order(self):
        order_id = self.buy(self.buyer)
        response = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/cancel/").status_code, 400)
        order_id = self.buy(self.buyer)
        self.client.force_authenticate(self.manager)
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
                "total": "0.01",
                "user": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "new")
        self.assertEqual(response.data["total"], "1000.00")
        self.assertEqual(Order.objects.get().user, self.buyer)

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
