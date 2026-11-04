from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product, ProductVariant
from orders.services import OrderError, cancel_by_customer, place_order


class VariantTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("variants")
        self.product = Product.objects.create(
            category=Category.objects.create(name="Одежда", slug="clothes"),
            name="Футболка",
            slug="shirt",
            sku="shirt",
            price=100,
            stock=50,
        )
        self.small = ProductVariant.objects.create(
            product=self.product, name="S красный", sku="s-red", price=120, stock=2
        )
        self.large = ProductVariant.objects.create(
            product=self.product, name="L синий", sku="l-blue", price=150, stock=10
        )
        self.cart = Cart.objects.create(user=self.user)

    def checkout(self):
        return place_order(
            user=self.user,
            cart=self.cart,
            delivery_method="pickup",
            full_name="Test",
            phone="+79135551234",
            email="test@example.test",
        )

    def test_separate_lines_price_snapshot_and_cancel(self):
        add_to_cart(self.cart, self.product, 1, variant=self.small)
        add_to_cart(self.cart, self.product, 2, variant=self.large)
        order = self.checkout()
        self.assertEqual(order.total, Decimal("420"))
        self.assertEqual(order.items.get(variant=self.small).variant_name, "S красный")
        self.small.refresh_from_db()
        self.assertEqual(self.small.stock, 1)
        cancel_by_customer(order, self.user)
        self.small.refresh_from_db()
        self.large.refresh_from_db()
        self.assertEqual((self.small.stock, self.large.stock), (2, 10))

    def test_variant_stock_cannot_borrow_from_other_variant(self):
        self.assertEqual(add_to_cart(self.cart, self.product, 100, variant=self.small), 2)
        ProductVariant.objects.filter(pk=self.small.pk).update(stock=1)
        with self.assertRaises(OrderError):
            self.checkout()
        self.assertEqual(self.cart.items.get().quantity, 2)

    def test_foreign_variant_rejected_and_explicit_choice_required(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            add_to_cart(self.cart, self.product)
        other = Product.objects.create(
            category=self.product.category, name="Other", slug="other", sku="other", price=1
        )
        with self.assertRaises(ValidationError):
            add_to_cart(self.cart, other, variant=self.small)
