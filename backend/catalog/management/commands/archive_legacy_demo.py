from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.caching import invalidate_catalog
from catalog.management.commands.seed_catalog import PRODUCTS
from catalog.models import Product


class Command(BaseCommand):
    help = "Предпросмотр или архивация только известных учебных товаров."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Архивировать показанные товары")

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {sku: (sku.lower(), name) for sku, _, name, *_ in PRODUCTS}
        expected.update(
            {f"DEMO-{i}": (f"demo-shirt-{i}", f"Демо-футболка {i}") for i in range(1, 6)}
        )
        # The sample import in examples/products.csv was part of the legacy demo.
        expected["CSV-DEMO"] = ("csv-demo", "Демонстрационная книга")
        candidates = (
            Product.objects.select_for_update()
            .filter(sku__in=expected, is_active=True)
            .order_by("sku")
        )
        selected = []
        for product in candidates:
            if (product.slug, product.name) == expected[product.sku]:
                selected.append(product.pk)
                self.stdout.write(f"{product.sku}: {product.name}")
            else:
                self.stdout.write(self.style.WARNING(f"Пропущен изменённый товар {product.sku}"))
        self.stdout.write(f"К архивации: {len(selected)}")
        if options["apply"]:
            Product.objects.filter(pk__in=selected).update(is_active=False)
            transaction.on_commit(invalidate_catalog)
            self.stdout.write("Архивация выполнена; товары и ссылки заказов сохранены.")
        else:
            self.stdout.write("Предпросмотр: изменений нет. Для записи добавьте --apply.")
