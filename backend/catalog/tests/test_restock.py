from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Category, Product, ProductVariant, StockSubscription
from catalog.restock import subscribe


class RestockTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Category.objects.create(name="Books", slug="books"),
            name="Book",
            sku="book",
            slug="book",
            price=10,
            stock=0,
        )

    def test_duplicate_subscription_and_zero_transition_sends_once(self):
        subscribe(self.product, "Buyer@example.test")
        subscribe(self.product, "buyer@example.test")
        self.assertEqual(StockSubscription.objects.count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.product.stock = 5
            self.product.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(StockSubscription.objects.get().completed)
        with self.captureOnCommitCallbacks(execute=True):
            self.product.stock = 6
            self.product.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_email_and_in_stock_rejected(self):
        with self.assertRaises(ValidationError):
            subscribe(self.product, "invalid")
        self.product.stock = 5
        self.product.save()
        with self.assertRaises(ValidationError):
            subscribe(self.product, "buyer@example.test")
        self.assertFalse(StockSubscription.objects.exists())

    def test_variant_restock_waits_for_commit(self):
        variant = ProductVariant.objects.create(
            product=self.product, name="S", sku="S", price=10, stock=0
        )
        subscribe(self.product, "buyer@example.test")
        with self.captureOnCommitCallbacks(execute=True):
            variant.stock = 2
            variant.save()
            self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(mail.outbox), 1)
