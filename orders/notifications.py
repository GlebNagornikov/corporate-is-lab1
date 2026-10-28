import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Order

logger = logging.getLogger(__name__)


def _send(order, template, subject):
    body = render_to_string(template, {"order": order})
    try:
        send_mail(subject, body, None, [order.email])
    except OSError:
        logger.exception("Не удалось отправить письмо по заказу №%s", order.pk)


def send_order_placed(order_id):
    order = Order.objects.prefetch_related("items").get(pk=order_id)
    _send(order, "orders/email/order_placed.txt", f"Заказ №{order.pk} оформлен")


def send_status_changed(order_id):
    order = Order.objects.get(pk=order_id)
    _send(
        order,
        "orders/email/status_changed.txt",
        f"Заказ №{order.pk}: {order.get_status_display().lower()}",
    )
