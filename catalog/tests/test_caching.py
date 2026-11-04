from django.test import TestCase, override_settings

from catalog.context_processors import categories
from catalog.models import Category, Product
from catalog.views import ProductDetailView


class CacheTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books", slug="books")
        self.product = Product.objects.create(
            category=self.category, name="Book", slug="book", sku="book", price=10
        )

    def test_menu_second_read_has_no_queries(self):
        with self.assertNumQueries(2):
            categories(None)
        with self.assertNumQueries(0):
            self.assertEqual(categories(None)["menu_categories"][0].name, "Books")

    def test_card_invalidates_after_price_category_and_review(self):
        view = ProductDetailView()
        view.kwargs = {"slug": "book"}
        self.assertEqual(view.get_object().price, 10)
        with self.assertNumQueries(0):
            view.get_object()
        self.product.price = 20
        self.product.save()
        self.assertEqual(view.get_object().price, 20)
        self.category.name = "New"
        self.category.save()
        self.assertEqual(view.get_object().category.name, "New")

    def test_unavailable_redis_keeps_catalog_usable(self):
        config = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "redis://127.0.0.1:1/1",
                "OPTIONS": {"IGNORE_EXCEPTIONS": True, "SOCKET_CONNECT_TIMEOUT": 0.01},
            }
        }
        with override_settings(CACHES=config):
            self.assertEqual(self.client.get("/product/book/").status_code, 200)

    def test_failed_cache_connection_is_not_repeated_for_every_operation(self):
        from unittest.mock import patch

        from redis.exceptions import ConnectionError

        from catalog.cache_backend import ResilientRedisCache

        backend = ResilientRedisCache(
            "redis://127.0.0.1:1/1", {"OPTIONS": {"IGNORE_EXCEPTIONS": False}}
        )
        with patch(
            "django_redis.cache.RedisCache.get", side_effect=ConnectionError("offline")
        ) as get:
            self.assertEqual(backend.get("card", "fallback"), "fallback")
            self.assertEqual(backend.get("menu", "fallback"), "fallback")
            self.assertFalse(backend.set("card", "data"))
            self.assertFalse(backend.delete("card"))
            get.assert_called_once()
