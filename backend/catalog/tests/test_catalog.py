from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from catalog.models import Category, Product, Review
from catalog.pagination import ProductPagination

User = get_user_model()


class CatalogTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.electronics = Category.objects.create(name="Электроника", slug="electronics")
        cls.laptops = Category.objects.create(
            name="Ноутбуки", slug="laptops", parent=cls.electronics
        )
        cls.books = Category.objects.create(name="Книги", slug="books")
        cls.laptop = Product.objects.create(
            category=cls.laptops,
            name="Ноутбук Lenovo",
            slug="lenovo",
            sku="NB-1",
            price=Decimal("50000"),
            stock=3,
            description="Лёгкий ноутбук для работы",
        )
        cls.book = Product.objects.create(
            category=cls.books,
            name="Книга «Чистый код»",
            slug="clean-code",
            sku="BK-1",
            price=Decimal("1000"),
            old_price=Decimal("1500"),
            stock=0,
        )
        cls.hidden = Product.objects.create(
            category=cls.books,
            name="Снят с продажи",
            slug="hidden",
            sku="X-1",
            price=Decimal("10"),
            is_active=False,
        )
        cls.user = User.objects.create_user("buyer", password="pass12345")


class SearchAndFilterTests(CatalogTestCase):
    def test_search_understands_russian_word_forms(self):
        found = Product.objects.search("ноутбуки")
        self.assertQuerySetEqual(found, [self.laptop])

    def test_typo_suggestions(self):
        self.assertIn(self.laptop, Product.objects.similar_to("ноутбк"))

    def test_parent_category_includes_subcategories(self):
        response = self.client.get(reverse("catalog:product_list"), {"category": "electronics"})
        self.assertEqual(list(response.context["products"]), [self.laptop])

    def test_inactive_product_is_hidden(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertNotIn(self.hidden, response.context["products"])
        response = self.client.get(self.hidden.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_list_page_has_constant_number_of_queries(self):
        for i in range(10):
            Product.objects.create(
                category=self.laptops,
                name=f"Ноутбук {i}",
                slug=f"nb-{i}",
                sku=f"NB-X{i}",
                price=Decimal("1000"),
            )
        # COUNT для пагинации, 2 запроса меню категорий, сами товары
        with self.assertNumQueries(4):
            self.client.get(reverse("catalog:product_list"))

    def test_in_stock_and_on_sale_filters(self):
        url = reverse("catalog:product_list")
        in_stock = self.client.get(url, {"in_stock": "true"}).context["products"]
        on_sale = self.client.get(url, {"on_sale": "true"}).context["products"]
        self.assertEqual(list(in_stock), [self.laptop])
        self.assertEqual(list(on_sale), [self.book])


class ReviewTests(CatalogTestCase):
    def test_rating_counts_only_published_reviews(self):
        other = User.objects.create_user("other", password="pass12345")
        Review.objects.create(
            product=self.laptop,
            author=self.user,
            rating=5,
            text="Отлично",
            status=Review.Status.APPROVED,
        )
        Review.objects.create(
            product=self.laptop, author=other, rating=1, text="Спам", status=Review.Status.REJECTED
        )
        product = Product.objects.with_rating().get(pk=self.laptop.pk)
        self.assertEqual(product.rating, 5)
        self.assertEqual(product.reviews_count, 1)

    def test_anonymous_cannot_post_review(self):
        url = reverse("catalog:review_create", args=[self.laptop.slug])
        response = self.client.post(url, {"rating": 5, "text": "Хорошо"})
        self.assertRedirects(response, f"{reverse('login')}?next={url}")


class ConstraintTests(CatalogTestCase):
    def test_old_price_must_be_greater_than_price(self):
        self.book.old_price = Decimal("500")
        with self.assertRaises(IntegrityError):
            self.book.save()


class CatalogApiTests(CatalogTestCase):
    def setUp(self):
        self.api = APIClient()

    def test_products_list_is_paginated_and_filtered(self):
        response = self.api.get("/api/catalog/products/", {"price_max": 2000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["sku"], "BK-1")
        self.assertEqual(response.data["results"][0]["discount_percent"], 33)

    def test_category_total_includes_all_pages_and_only_visible_products(self):
        Product.objects.create(
            category=self.books, name="Справочник", slug="guide", sku="BK-2", price=Decimal("5.45")
        )
        with patch.object(ProductPagination, "page_size", 1):
            response = self.api.get("/api/catalog/products/", {"category": "books"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["total"], "1005.45")

    def test_typo_suggestion_preserves_pagination_and_respects_filters(self):
        url = "/api/catalog/products/"
        typo = {"q": "ноутбк", "category": "electronics"}
        response = self.api.get(url, typo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
        self.assertEqual(response.data["suggestion"], self.laptop.name)

        corrected = self.api.get(url, {**typo, "q": response.data["suggestion"]})
        self.assertEqual(corrected.data["count"], 1)
        self.assertIsNone(corrected.data["suggestion"])
        self.assertIsNone(self.api.get(url, {**typo, "category": "books"}).data["suggestion"])
