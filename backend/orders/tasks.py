import logging
from smtplib import SMTPException

from celery import shared_task
from django.db import transaction
from kombu.exceptions import OperationalError

from .models import EmailNotification

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(OSError, SMTPException),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 10},
)
def send_notification(notification_id):
    from .notifications import send_order_placed, send_status_changed

    with transaction.atomic():
        notification = EmailNotification.objects.select_for_update().get(pk=notification_id)
        if notification.sent:
            return
        if notification.kind == "placed":
            send_order_placed(notification.order_id)
        else:
            send_status_changed(notification.order_id, notification.status_snapshot)
        notification.sent = True
        notification.save(update_fields=["sent"])


def dispatch_notification(notification_id):
    try:
        from config.request_logging import request_id

        send_notification.apply_async(args=[notification_id], headers={"request_id": request_id()})
    except (OperationalError, OSError):
        logger.exception(
            "Не удалось поставить письмо в очередь; оно сохранено в БД",
            extra={"notification_id": notification_id},
        )


def queue_order_email(order, kind):
    notification = EmailNotification.objects.create(
        order=order, kind=kind, status_snapshot=order.status
    )
    transaction.on_commit(lambda: dispatch_notification(notification.pk))
