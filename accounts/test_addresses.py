from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.addresses import delete_address, save_address
from accounts.models import Address
from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product
from orders.services import OrderError, place_order

DATA = {"label": "Дом", "city": "Город", "street": "Улица", "house": "1"}


class AddressTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("address")
        self.other = get_user_model().objects.create_user("other")

    def test_primary_switch_delete_and_database_constraint(self):
        first = save_address(self.user, DATA)
        second = save_address(self.user, {**DATA, "label": "Работа", "is_primary": True})
        first.refresh_from_db()
        self.assertFalse(first.is_primary)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Address.objects.create(user=self.user, **DATA, is_primary=True)
        delete_address(self.user, second.pk)
        first.refresh_from_db()
        self.assertTrue(first.is_primary)

    def test_foreign_address_cannot_be_opened_or_changed(self):
        address = save_address(self.other, DATA)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/accounts/addresses/{address.pk}/").status_code, 404)
        with self.assertRaises(PermissionDenied):
            save_address(self.user, DATA, address.pk)

    def test_order_address_is_snapshot_and_foreign_checkout_rejected(self):
        address = save_address(self.user, DATA)
        product = Product.objects.create(
            category=Category.objects.create(name="Books", slug="books"),
            name="Book",
            slug="book",
            sku="book",
            price=10,
            stock=5,
        )
        cart = Cart.objects.create(user=self.user)
        add_to_cart(cart, product)
        args = dict(
            user=self.user,
            cart=cart,
            delivery_method="courier",
            full_name="Buyer",
            phone="+79135551234",
            email="buyer@example.test",
        )
        with self.assertRaises(OrderError):
            place_order(**args, address_book=save_address(self.other, DATA))
        order = place_order(**args, address_book=address)
        save_address(self.user, {**DATA, "house": "2"}, address.pk)
        order.refresh_from_db()
        self.assertEqual(order.address, "Город, Улица, 1")
