from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Category, Product, ProductVariant, StockSubscription
from catalog.restock import deliver_restock, subscribe


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
        self.assertIn("/products/book", mail.outbox[0].body)
        self.assertTrue(StockSubscription.objects.get().completed)
        with self.captureOnCommitCallbacks(execute=True):
            self.product.stock = 6
            self.product.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_variant_deletion_recalculates_price_and_stock_including_last_variant(self):
        first = ProductVariant.objects.create(
            product=self.product, name="A", sku="a", price=50, stock=4
        )
        second = ProductVariant.objects.create(
            product=self.product, name="B", sku="b", price=150, stock=3
        )
        first.delete()
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.price), (3, 150))
        ProductVariant.objects.filter(pk=second.pk).delete()
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.price), (0, 150))

    def test_delayed_email_waits_until_book_is_available_again(self):
        subscription = subscribe(self.product, "buyer@example.test")
        deliver_restock(self.product.pk)
        subscription.refresh_from_db()
        self.assertFalse(subscription.completed)
        self.assertEqual(len(mail.outbox), 0)

        with self.captureOnCommitCallbacks(execute=True):
            self.product.is_active = False
            self.product.stock = 2
            self.product.save()
        self.assertEqual(len(mail.outbox), 0)
        with self.captureOnCommitCallbacks(execute=True):
            self.product.is_active = True
            self.product.save(update_fields=["is_active"])
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
