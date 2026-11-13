import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITransactionTestCase

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product
from orders.models import Order, OrderItem, Payment
from orders.payments import begin_payment, signature
from orders.tests.test_api import CUSTOMER


@override_settings(PAYMENT_WEBHOOK_SECRET="concurrent-payment-test-secret")
class ConcurrentOrderTests(APITransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        category = Category.objects.create(name="Книги", slug="books")
        self.book = Product.objects.create(
            category=category, name="Last copy", slug="last-copy", sku="LAST", price=100, stock=1
        )

    def post_concurrently(self, *requests):
        ready = Barrier(len(requests), timeout=10)

        def post(request):
            url, buyer, body, kwargs = request
            try:
                client = APIClient()
                if buyer is not None:
                    client.force_authenticate(buyer)
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_pid = cursor.fetchone()[0]
                ready.wait()
                response = client.post(url, body, **kwargs)
                return backend_pid, response.status_code, response.json()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as workers:
            responses = list(workers.map(post, requests))
        self.assertEqual(len({pid for pid, _, _ in responses}), len(requests))
        return [(status, body) for _, status, body in responses]

    def test_two_buyers_cannot_buy_the_same_last_copy(self):
        carts = []
        for username in ("first-buyer", "second-buyer"):
            buyer = get_user_model().objects.create_user(username)
            cart = Cart.objects.create(user=buyer)
            add_to_cart(cart, self.book, 1)
            carts.append(cart)

        results = self.post_concurrently(
            *(("/api/orders/", cart.user, CUSTOMER, {"format": "json"}) for cart in carts)
        )

        self.assertEqual(sorted(status for status, _ in results), [201, 400], results)
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(
            list(order.history.values_list("to_status", flat=True)), [Order.Status.NEW]
        )
        self.assertEqual(
            list(OrderItem.objects.values_list("product_id", "quantity")), [(self.book.pk, 1)]
        )
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 0)
        self.assertEqual(self.book.variants.get(is_default=True).stock, 0)
        for cart, (status, body) in zip(carts, results, strict=True):
            if status == 201:
                self.assertEqual((order.pk, order.user_id), (body["id"], cart.user_id))
                self.assertFalse(cart.items.exists())
            else:
                self.assertIn("осталось только 0", body["detail"])
                self.assertEqual(cart.items.get().quantity, 1)

    def test_two_success_callbacks_apply_the_same_payment_once(self):
        buyer = get_user_model().objects.create_user("payer")
        cart = Cart.objects.create(user=buyer)
        add_to_cart(cart, self.book, 1)
        client = APIClient()
        client.force_authenticate(buyer)
        checkout = client.post("/api/orders/", CUSTOMER, format="json")
        self.assertEqual(checkout.status_code, 201, checkout.data)
        order = Order.objects.get(pk=checkout.data["id"])
        payment = begin_payment(order, buyer)
        body = json.dumps({"payment_id": str(payment.pk), "outcome": "success"}).encode()
        callback = (
            reverse("payment-webhook"),
            None,
            body,
            {"content_type": "application/json", "HTTP_X_PAYMENT_SIGNATURE": signature(body)},
        )

        self.assertEqual(
            self.post_concurrently(callback, callback), [(200, {"status": "success"})] * 2
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(payment.status, "success")
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.items.get().quantity, 1)
        self.assertCountEqual(
            order.history.values_list("to_status", flat=True), [Order.Status.NEW, Order.Status.PAID]
        )
        self.assertEqual(self.book.stock, 0)
        self.assertEqual(self.book.variants.get(is_default=True).stock, 0)
