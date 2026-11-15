import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Order

logger = logging.getLogger(__name__)


def _send(order, template, subject, **context):
    body = render_to_string(template, {"order": order, **context})
    try:
        send_mail(subject, body, None, [order.email])
    except OSError:
        logger.exception("Не удалось отправить письмо по заказу №%s", order.pk)
        raise


def send_order_placed(order_id):
    order = Order.objects.prefetch_related("items").get(pk=order_id)
    _send(order, "orders/email/order_placed.txt", f"Заказ №{order.pk} оформлен")


def send_status_changed(order_id, status_snapshot=None):
    order = Order.objects.get(pk=order_id)
    if status_snapshot:
        order.status = status_snapshot
    cancellation_reason = None
    if order.status == Order.Status.CANCELLED:
        cancellation_reason = (
            order.history.filter(to_status=Order.Status.CANCELLED)
            .order_by("-created_at", "-pk")
            .values_list("comment", flat=True)
            .first()
        )
    _send(
        order,
        "orders/email/status_changed.txt",
        f"Заказ №{order.pk}: {order.get_status_display().lower()}",
        cancellation_reason=cancellation_reason,
    )
