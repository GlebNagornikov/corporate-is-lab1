from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.importing import import_products
from catalog.models import Category, Product, ProductVariant

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
