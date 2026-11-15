import logging
import time

from django.conf import settings
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from .models import Order

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 15
ORDER_CHANGED = b"event: order-changed\ndata: {}\n\n"


def order_channel(order_id):
    return f"shop:orders:{order_id}:status"


def publish_order_change(order_id):
    with Redis.from_url(
        settings.ORDER_EVENTS_REDIS_URL, socket_connect_timeout=2, socket_timeout=2
    ) as broker:
        broker.publish(order_channel(order_id), "changed")


async def order_events(order_id, user_id, password, expires_at):
    access = Order.objects.filter(
        pk=order_id, user_id=user_id, user__is_active=True, user__password=password
    )
    try:
        async with (
            AsyncRedis.from_url(
                settings.ORDER_EVENTS_REDIS_URL, socket_connect_timeout=2, socket_timeout=5
            ) as broker,
            broker.pubsub() as subscription,
        ):
            await subscription.subscribe(order_channel(order_id))
            heartbeat_at = time.monotonic() + HEARTBEAT_SECONDS
            while (remaining := expires_at - time.time()) > 0:
                wait = min(remaining, max(0, heartbeat_at - time.monotonic()))
                message = await subscription.get_message(timeout=wait)
                if time.time() >= expires_at:
                    return
                heartbeat_due = time.monotonic() >= heartbeat_at
                if not message and not heartbeat_due:
                    continue
                if not await access.aexists() or time.time() >= expires_at:
                    return
                if heartbeat_due:
                    heartbeat_at = time.monotonic() + HEARTBEAT_SECONDS
                # Подтверждение подписки запрашивает свежий снимок и после переподключения Redis.
                if message:
                    yield ORDER_CHANGED
                else:
                    yield b": heartbeat\n\n"
    except RedisError:
        logger.warning("Order event stream disconnected", exc_info=True)
