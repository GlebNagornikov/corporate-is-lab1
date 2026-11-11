from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from rest_framework.test import APITestCase

from catalog.models import BookEdition, Category, Product, ProductVariant, RestockNotification
from catalog.restock import subscribe

NOTIFICATIONS = "/api/notifications/"
UNREAD = "/api/notifications/unread/"


class RestockAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.buyer = users.create_user("buyer", email="buyer@example.test")
        cls.other = users.create_user("other", email=cls.buyer.email)
        cls.manager = users.create_user("manager")
        call_command("setup_groups", stdout=StringIO())
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))
        cls.product = Product.objects.create(
            category=Category.objects.create(name="Книги", slug="books"),
            name="Книга",
            sku="book",
            slug="book",
            price=100,
            stock=0,
        )
        BookEdition.objects.create(
            product=cls.product,
            author="Автор",
            publisher="Полка",
            year=2025,
            language="Русский",
            binding=BookEdition.Binding.HARDCOVER,
            pages=100,
        )

    @property
    def subscription_url(self):
        return f"/api/restock/{self.product.pk}/"

    def test_variant_restock_through_manager_api_and_personal_access(self):
        variant = ProductVariant.objects.create(
            product=self.product, name="Склад", sku="variant", price=100, stock=0
        )
        url = f"/api/manager/catalog/{self.product.pk}/variants/{variant.pk}/"
        self.assertEqual(self.client.post(self.subscription_url).status_code, 401)
        self.assertEqual(self.client.get(NOTIFICATIONS).status_code, 401)
        self.assertEqual(self.client.post(UNREAD).status_code, 401)
        self.client.force_authenticate(self.buyer)
        for _ in range(2):
            self.assertEqual(self.client.post(self.subscription_url).data, {"subscribed": True})
        self.assertEqual(self.client.get(self.subscription_url).data, {"subscribed": True})
        self.assertEqual(self.client.get(NOTIFICATIONS).data, [])
        subscribe(self.product, self.buyer.email)

        self.client.force_authenticate(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            for stock in (1, 1, 2):
                self.assertEqual(self.client.patch(url, {"stock": stock}).status_code, 200)

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(NOTIFICATIONS).data, [])
        self.assertEqual(self.client.get(UNREAD).data, {"unread_count": 0})
        self.assertEqual(self.client.post(UNREAD).status_code, 204)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get(UNREAD).data, {"unread_count": 1})
        (notice,) = self.client.get(NOTIFICATIONS).data
        self.assertEqual(notice["product_slug"], self.product.slug)
        self.assertIsNone(notice["read_at"])
        self.assertEqual(self.client.get(self.subscription_url).data, {"subscribed": False})
        self.assertEqual(self.client.post(self.subscription_url).status_code, 400)
        self.assertEqual(self.client.post(UNREAD).status_code, 204)
        self.assertEqual(self.client.get(UNREAD).data, {"unread_count": 0})
        self.assertIsNotNone(self.client.get(NOTIFICATIONS).data[0]["read_at"])

    def test_product_restock_rollback_and_resubscription(self):
        url = f"/api/manager/catalog/{self.product.pk}/"
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(self.subscription_url).status_code, 200)
        self.client.force_authenticate(self.manager)
        with self.captureOnCommitCallbacks() as callbacks, transaction.atomic():
            self.assertEqual(self.client.patch(url, {"stock": 1}).status_code, 200)
            transaction.set_rollback(True)
        self.assertFalse(callbacks)
        self.assertTrue(RestockNotification.objects.filter(notified_at=None).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(self.client.patch(url, {"stock": 1}).status_code, 200)
        self.assertEqual(self.client.patch(url, {"stock": 0}).status_code, 200)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(self.subscription_url).status_code, 200)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.patch(url, {"stock": 1}).status_code, 200)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get(UNREAD).data, {"unread_count": 2})
