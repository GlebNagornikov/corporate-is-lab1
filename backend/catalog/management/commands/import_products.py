from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from catalog.importing import import_products


class Command(BaseCommand):
    help = "Транзакционный импорт товаров по артикулу из UTF-8 CSV"

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            with open(options["file"], encoding="utf-8-sig", newline="") as stream:
                count = import_products(stream, dry_run=options["dry_run"])
        except (ValidationError, OSError, UnicodeError) as error:
            message = (
                "\n".join(error.messages) if isinstance(error, ValidationError) else str(error)
            )
            raise CommandError(message) from error
        self.stdout.write(f"Строк обработано: {count}; dry-run={options['dry_run']}")
