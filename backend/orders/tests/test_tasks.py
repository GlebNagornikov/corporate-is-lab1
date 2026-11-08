from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from orders.models import EmailNotification, Order
from orders.tasks import queue_order_email, send_notification


class MailTaskTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("task")
        self.order = Order.objects.create(
            user=user, full_name="Task", email="task@example.test", phone="1", subtotal=10, total=10
        )

    def test_task_is_enqueued_only_after_commit(self):
        with patch("orders.tasks.send_notification.apply_async") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                queue_order_email(self.order, "placed")
                delay.assert_not_called()
            delay.assert_called_once()

    def test_duplicate_delivery_is_ignored(self):
        job = EmailNotification.objects.create(order=self.order, kind="placed")
        send_notification.apply(args=[job.pk]).get()
        send_notification.apply(args=[job.pk]).get()
        self.assertEqual(len(mail.outbox), 1)
        job.refresh_from_db()
        self.assertTrue(job.sent)

    def test_smtp_failure_retries_and_job_remains_recoverable(self):
        job = EmailNotification.objects.create(order=self.order, kind="placed")
        with patch(
            "orders.notifications.send_mail", side_effect=OSError("SMTP unavailable")
        ) as send:
            result = send_notification.apply(args=[job.pk])
        self.assertTrue(result.failed())
        self.assertGreater(send.call_count, 1)
        job.refresh_from_db()
        self.assertFalse(job.sent)
        send_notification.apply(args=[job.pk]).get()
        job.refresh_from_db()
        self.assertTrue(job.sent)
