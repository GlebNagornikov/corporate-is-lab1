from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product, WishlistItem
from catalog.wishlist import set_favorite


class WishlistTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("favorite")
        self.other = get_user_model().objects.create_user("other")
        self.product = Product.objects.create(
            category=Category.objects.create(name="Books", slug="books"),
            name="Book",
            sku="book",
            slug="book",
            price=10,
        )

    def test_duplicate_add_and_remove(self):
        set_favorite(self.user, self.product)
        set_favorite(self.user, self.product)
        self.assertEqual(WishlistItem.objects.count(), 1)
        set_favorite(self.user, self.product, False)
        self.assertFalse(WishlistItem.objects.exists())

    def test_guest_redirect_and_inactive_product_display(self):
        self.assertEqual(self.client.post(f"/wishlist/{self.product.pk}/").status_code, 302)
        set_favorite(self.user, self.product)
        self.product.is_active = False
        self.product.save()
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/wishlist/"), "нет в продаже")

    def test_api_ownership_and_input_validation(self):
        set_favorite(self.other, self.product)
        client = APIClient()
        self.assertEqual(client.get("/api/wishlist/").status_code, 401)
        client.force_authenticate(self.user)
        self.assertEqual(client.get("/api/wishlist/").data, [])
        self.assertEqual(client.post("/api/wishlist/", {"product": 99999}).status_code, 400)
        self.assertEqual(
            client.post("/api/wishlist/", {"product": self.product.pk}).status_code, 201
        )
        self.assertEqual(client.delete(f"/api/wishlist/{self.product.pk}/").status_code, 204)
        self.assertTrue(WishlistItem.objects.filter(user=self.other).exists())
