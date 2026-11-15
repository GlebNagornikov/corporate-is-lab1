import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.importing import import_products
from catalog.models import Category, Product, ProductVariant, RestockNotification

HEADER = "sku,name,slug,category,price,stock\n"


class ImportTests(TestCase):
    def setUp(self):
        Category.objects.create(name="Books", slug="books")

    def test_idempotent_update_and_variant(self):
        data = HEADER + "BOOK,Book,book,books,10,5\n"
        self.assertEqual(import_products(StringIO(data)), 1)
        import_products(StringIO(data.replace(",10,5", ",12,6")))
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().price, 12)
        import_products(
            StringIO(
                HEADER.rstrip() + ",variant_sku,variant_name\nBOOK,Book,book,books,12,6,V1,Paper\n"
            )
        )
        self.assertEqual(ProductVariant.objects.get().sku, "V1")

    def test_all_errors_reported_and_no_partial_write(self):
        with self.assertRaises(ValidationError) as raised:
            import_products(
                StringIO(
                    HEADER + "OK,Good,good,books,10,5\n"
                    "BAD,Bad,bad,books,-1,2\n"
                    "MISS,Missing,missing,absent,1,1\n"
                )
            )
        self.assertIn("Строка 3", str(raised.exception))
        self.assertIn("Строка 4", str(raised.exception))
        self.assertFalse(Product.objects.exists())

    def test_dry_run_and_admin_permission(self):
        import_products(StringIO(HEADER + "BOOK,Book,book,books,10,5\n"), dry_run=True)
        self.assertFalse(Product.objects.exists())
        user = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/catalog/product/import-csv/").status_code, 403)

    def test_csv_parser_error_is_reported_before_writing_any_products(self):
        oversized_name = "x" * (csv.field_size_limit() + 1)
        data = HEADER + f"OK,Good,good,books,10,5\nBAD,{oversized_name},bad,books,10,5\n"
        with self.assertRaisesMessage(ValidationError, "Не удалось прочитать CSV"):
            import_products(StringIO(data))
        self.assertFalse(Product.objects.exists())

    def test_csv_does_not_overwrite_warehouse_stock_or_notify_for_unavailable_book(self):
        import_products(StringIO(HEADER + "BOOK,Book,book,books,10,0\n"))
        product = Product.objects.get()
        user = get_user_model().objects.create_user("subscriber")
        RestockNotification.objects.create(user=user, product=product)
        header = HEADER.rstrip() + ",variant_sku,variant_price,variant_stock\n"
        import_products(StringIO(header + "BOOK,Book,book,books,10,5,V1,20,0\n"))
        import_products(StringIO(HEADER + "BOOK,Renamed,book,books,10,5\n"))
        product.refresh_from_db()
        self.assertEqual((product.name, product.price, product.stock), ("Renamed", 20, 0))
        self.assertIsNone(RestockNotification.objects.get().notified_at)

    def test_csv_rejects_combined_warehouse_stock_overflow_in_both_modes(self):
        header = HEADER.rstrip() + ",variant_sku\n"
        import_products(StringIO(header + "BOOK,Book,book,books,10,2147483647,V1\n"))
        for dry_run in (True, False):
            with (
                self.subTest(dry_run=dry_run),
                self.assertRaisesMessage(ValidationError, "Слишком большой суммарный остаток."),
            ):
                import_products(
                    StringIO(header + "BOOK,Book,book,books,10,1,V2\n"), dry_run=dry_run
                )
        self.assertEqual(ProductVariant.objects.count(), 1)
