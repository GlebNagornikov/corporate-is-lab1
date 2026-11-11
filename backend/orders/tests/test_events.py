from asyncio import wait_for
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import AsyncClient, TransactionTestCase
from redis import Redis
from rest_framework_simplejwt.tokens import AccessToken

from orders.events import ORDER_CHANGED, order_channel
from orders.models import Order
from orders.services import change_status


class OrderEventsTests(TransactionTestCase):
    def setUp(self):
        users = get_user_model().objects
        self.buyer = users.create_user(username="event-buyer")
        self.other = users.create_superuser(username="event-other")
        self.order = Order.objects.create(
            user=self.buyer,
            status=Order.Status.PAID,
            email="event-buyer@example.test",
            subtotal=100,
            total=100,
        )
        self.url = f"/api/orders/{self.order.pk}/events/"
        self.buyer_auth = f"Bearer {AccessToken.for_user(self.buyer)}"

    @patch("orders.events.HEARTBEAT_SECONDS", 0.1)
    async def test_stream_checks_bearer_and_owner_before_opening(self):
        client = AsyncClient()
        self.assertEqual((await client.get(self.url)).status_code, 401)
        other_auth = f"Bearer {AccessToken.for_user(self.other)}"
        response = await client.get(self.url, headers={"Authorization": other_auth})
        self.assertEqual(response.status_code, 404)
        response = await client.get(self.url, headers={"Authorization": self.buyer_auth})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        stream = response.streaming_content
        self.assertEqual(await anext(stream), ORDER_CHANGED)
        await get_user_model().objects.filter(pk=self.buyer.pk).aupdate(is_active=False)
        self.assertIsNone(await anext(stream, None))
        response.close()

    async def test_stream_closes_when_access_expires(self):
        access = AccessToken.for_user(self.buyer)
        access.set_exp(lifetime=timedelta(seconds=3))
        response = await AsyncClient().get(self.url, headers={"Authorization": f"Bearer {access}"})
        self.assertEqual(response.status_code, 200)
        stream = response.streaming_content
        self.assertEqual(await anext(stream), ORDER_CHANGED)
        self.assertIsNone(await wait_for(anext(stream, None), timeout=4))
        response.close()

    def test_broker_receives_status_only_after_commit(self):
        with Redis.from_url(settings.ORDER_EVENTS_REDIS_URL) as broker, broker.pubsub() as sub:
            sub.subscribe(order_channel(self.order.pk))
            self.assertEqual(sub.get_message(timeout=2)["type"], "subscribe")
            with transaction.atomic():
                change_status(self.order, Order.Status.CONFIRMED, by=self.other)
                self.assertIsNone(sub.get_message(timeout=0.1))
                transaction.set_rollback(True)
            self.assertIsNone(sub.get_message(timeout=0.1))
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, Order.Status.PAID)
            with transaction.atomic():
                change_status(self.order, Order.Status.CONFIRMED, by=self.other)
                self.assertIsNone(sub.get_message(timeout=0.1))
            self.assertEqual(sub.get_message(timeout=2)["data"], b"changed")
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, Order.Status.CONFIRMED)
