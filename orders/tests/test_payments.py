import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from orders.models import Order, Payment
from orders.payments import begin_payment, signature
from orders.services import OrderError, cancel_by_customer, change_status


@override_settings(PAYMENT_WEBHOOK_SECRET="payment-test-secret")
class PaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("payer")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Buyer",
            phone="+79135551234",
            email="buyer@example.test",
            subtotal=10,
            total=10,
        )

    def callback(self, payment, outcome="success", signed=True):
        body = json.dumps({"payment_id": str(payment.pk), "outcome": outcome}).encode()
        return self.client.post(
            "/payments/webhook/",
            body,
            content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE=signature(body) if signed else "wrong",
        )

    def test_invalid_signature_changes_nothing(self):
        payment = begin_payment(self.order, self.user)
        self.assertEqual(self.callback(payment, signed=False).status_code, 403)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, "new")
        self.assertEqual(payment.status, "pending")

    def test_success_is_idempotent_and_customer_cannot_cancel_paid(self):
        payment = begin_payment(self.order, self.user)
        self.assertEqual(self.callback(payment).status_code, 200)
        self.assertEqual(self.callback(payment).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        self.assertEqual(self.order.history.count(), 1)
        with self.assertRaises(OrderError):
            cancel_by_customer(self.order, self.user)
        manager = get_user_model().objects.create_user("manager")
        change_status(self.order, "cancelled", by=manager)
        self.assertEqual(Payment.objects.count(), 1)

    def test_decline_retry_and_foreign_order(self):
        other = get_user_model().objects.create_user("other")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/payments/gateway/{self.order.pk}/").status_code, 404)
        self.client.force_login(self.user)
        response = self.client.post(f"/payments/gateway/{self.order.pk}/", {"outcome": "failed"})
        self.assertEqual(response.status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual(self.callback(payment, "failed").status_code, 200)
        self.assertEqual(self.order.status, "new")
        self.assertEqual(self.callback(begin_payment(self.order, self.user)).status_code, 200)

    def test_spa_payment_allows_decline_then_success_without_double_charge(self):
        client = APIClient()
        url = f"/api/orders/{self.order.pk}/simulate-payment/"
        client.force_authenticate(self.user)
        declined = client.post(url, {"outcome": "failed"})
        self.assertEqual(declined.status_code, 200, declined.data)
        self.assertEqual(declined.data["status"], "new")
        self.assertTrue(declined.data["can_pay"])
        paid = client.post(url, {"outcome": "success"})
        self.assertEqual(paid.status_code, 200, paid.data)
        self.assertEqual(paid.data["status"], "paid")
        self.assertFalse(paid.data["can_pay"])
        self.assertEqual(client.post(url, {"outcome": "success"}).status_code, 400)
        self.assertEqual(self.order.payments.filter(status="success").count(), 1)
        self.assertEqual(self.order.payments.filter(status="failed").count(), 1)
        self.assertEqual(self.order.history.filter(to_status="paid").count(), 1)

    def test_spa_payment_is_owner_only_even_when_manager_can_view_order(self):
        client = APIClient()
        url = f"/api/orders/{self.order.pk}/simulate-payment/"
        self.assertEqual(client.post(url, {"outcome": "success"}).status_code, 401)
        manager = get_user_model().objects.create_user("viewer")
        manager.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="orders", codename__in=["view_order", "change_order"]
            )
        )
        client.force_authenticate(manager)
        detail = client.get(f"/api/orders/{self.order.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.data["can_pay"])
        self.assertEqual(client.post(url, {"outcome": "success"}).status_code, 404)
        self.assertFalse(self.order.payments.exists())
