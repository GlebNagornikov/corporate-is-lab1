from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product
from orders.models import Order, PromoCode
from orders.services import OrderError, cancel_by_customer, change_status, place_order

User = get_user_model()
CUSTOMER = {
    "full_name": "Иванова Анна",
    "phone": "+79130000000",
    "email": "anna@example.com",
    "delivery_method": Order.Delivery.PICKUP,
}


class OrderServiceTests(TestCase):
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
        cls.pen = Product.objects.create(
            category=category,
            name="Ручка",
            slug="pen",
            sku="PN-1",
            price=Decimal("100"),
            stock=1,
        )
        cls.user = User.objects.create_user("buyer", password="pass12345")
        cls.manager = User.objects.create_user("manager", password="pass12345")

    def setUp(self):
        self.cart = Cart.objects.create(user=self.user)

    def order(self, **extra):
        return place_order(user=self.user, cart=self.cart, **{**CUSTOMER, **extra})

    def test_place_order_takes_stock_and_freezes_price(self):
        add_to_cart(self.cart, self.book, 2)
        order = self.order()
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 3)
        self.assertEqual(order.total, Decimal("2000"))
        self.assertFalse(self.cart.items.exists())
        self.book.price = Decimal("9999")
        self.book.save()
        self.assertEqual(order.items.get().price, Decimal("1000"))

    def test_not_enough_stock_rolls_back_everything(self):
        add_to_cart(self.cart, self.book, 2)
        add_to_cart(self.cart, self.pen, 1)
        Product.objects.filter(pk=self.pen.pk).update(stock=0)
        with self.assertRaisesMessage(OrderError, "Ручка"):
            self.order()
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.cart.items.count(), 2)

    def test_promo_code_and_courier_delivery(self):
        now = timezone.now()
        promo = PromoCode.objects.create(
            code="student10",
            discount_percent=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
        )
        add_to_cart(self.cart, self.book, 2)
        order = self.order(
            promo_code="STUDENT10",
            delivery_method=Order.Delivery.COURIER,
            address="ул. Каменская, 56",
        )
        self.assertEqual(order.discount, Decimal("200.00"))
        self.assertEqual(order.delivery_cost, Decimal("500"))
        self.assertEqual(order.total, Decimal("2300.00"))
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)

    def test_expired_promo_code_is_rejected(self):
        now = timezone.now()
        PromoCode.objects.create(
            code="OLD",
            discount_percent=50,
            valid_from=now - timedelta(days=10),
            valid_until=now - timedelta(days=1),
        )
        add_to_cart(self.cart, self.book, 1)
        with self.assertRaises(OrderError):
            self.order(promo_code="old")

    def test_email_is_sent_after_commit(self):
        add_to_cart(self.cart, self.book, 1)
        with self.captureOnCommitCallbacks(execute=True):
            order = self.order()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"№{order.pk}", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["anna@example.com"])

    def test_cancel_returns_stock_and_writes_history(self):
        add_to_cart(self.cart, self.book, 2)
        order = self.order()
        cancel_by_customer(order, self.user)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 5)
        self.assertEqual(
            list(order.history.values_list("to_status", flat=True)),
            [Order.Status.NEW, Order.Status.CANCELLED],
        )

    def test_status_workflow(self):
        add_to_cart(self.cart, self.book, 1)
        order = self.order()
        change_status(order, Order.Status.CONFIRMED, by=self.manager)
        with self.assertRaises(OrderError):
            change_status(order, Order.Status.DELIVERED, by=self.manager)
        with self.assertRaises(OrderError):
            cancel_by_customer(order, self.user)

    def test_email_failure_is_logged_without_rolling_back_order(self):
        add_to_cart(self.cart, self.book, 2)
        with (
            patch("orders.notifications.send_mail", side_effect=OSError("SMTP unavailable")),
            self.assertLogs("orders.notifications", level="ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            order = self.order()
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertEqual(order.total, Decimal("2000"))
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 3)
        self.assertFalse(self.cart.items.exists())
        self.assertEqual(len(logs.records), 1)
        self.assertIn(str(order.pk), logs.records[0].getMessage())
        self.assertIsNotNone(logs.records[0].exc_info)
