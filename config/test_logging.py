import json
import logging
from unittest.mock import patch

from django.test import TestCase

from config.request_logging import JSONFormatter, context


class LoggingTests(TestCase):
    def test_header_preserved_and_context_is_cleared(self):
        response = self.client.get("/healthz/", HTTP_X_REQUEST_ID="test-request-123")
        self.assertEqual(response["X-Request-ID"], "test-request-123")
        self.assertIsNone(context.get())

    def test_invalid_header_replaced_and_json_fields_present(self):
        response = self.client.get("/healthz/", HTTP_X_REQUEST_ID="x" * 200)
        self.assertEqual(len(response["X-Request-ID"]), 32)
        record = logging.LogRecord("orders", logging.INFO, "", 0, "Order created", (), None)
        record.order_id = 15
        parsed = json.loads(JSONFormatter().format(record))
        self.assertTrue(
            {"time", "level", "logger", "message", "request_id", "user_id", "path"}.issubset(parsed)
        )
        self.assertEqual(parsed["order_id"], 15)

    def test_request_id_propagates_to_celery(self):
        from orders.tasks import dispatch_notification

        token = context.set({"request_id": "trace-payment"})
        try:
            with patch("orders.tasks.send_notification.apply_async") as send:
                dispatch_notification(123)
                self.assertEqual(send.call_args.kwargs["headers"]["request_id"], "trace-payment")
        finally:
            context.reset(token)
