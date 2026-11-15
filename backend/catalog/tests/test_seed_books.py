import io
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import BookEdition, Category, Product


class SeedDemoTests(TestCase):
    def test_repeat_preserves_price_stock_image_and_password(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            call_command("seed_demo", password="InitialPass2026!", stdout=io.StringIO())
            self.assertGreaterEqual(BookEdition.objects.count(), 20)
            self.assertGreaterEqual(Category.objects.count(), 3)
            product = Product.objects.get(sku="BOOK-CLASSIC-001")
            image = product.image.name
            product.price, product.stock = Decimal("1234.00"), 17
            product.save(update_fields=["price", "stock"])
            call_command("seed_demo", password="DifferentPass2026!", stdout=io.StringIO())
            product.refresh_from_db()
            self.assertEqual(
                (product.price, product.stock, product.image.name), (Decimal("1234.00"), 17, image)
            )
            self.assertEqual(Product.objects.count(), BookEdition.objects.count())
            buyer = get_user_model().objects.get(username="buyer_demo")
            self.assertTrue(buyer.check_password("InitialPass2026!"))
            self.assertTrue(get_user_model().objects.get(username="manager_demo").is_staff)
