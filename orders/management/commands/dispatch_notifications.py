from django.core.management.base import BaseCommand

from orders.models import EmailNotification
from orders.tasks import dispatch_notification


class Command(BaseCommand):
    help = "Повторно поставить сохранённые неотправленные письма в очередь"

    def handle(self, *args, **options):
        ids = list(EmailNotification.objects.filter(sent=False).values_list("pk", flat=True))
        for pk in ids:
            dispatch_notification(pk)
        self.stdout.write(f"Писем поставлено в очередь: {len(ids)}")
