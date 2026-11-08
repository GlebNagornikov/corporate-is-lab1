from smtplib import SMTPException

from celery import shared_task


@shared_task(
    autoretry_for=(OSError, SMTPException),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 10},
)
def send_restock(product_id):
    from .restock import deliver_restock

    deliver_restock(product_id)
