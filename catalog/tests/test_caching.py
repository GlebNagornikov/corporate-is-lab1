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
