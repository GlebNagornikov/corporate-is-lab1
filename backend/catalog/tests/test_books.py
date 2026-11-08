import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import BookEdition, Category, Product, ProductImage


class BookCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        genre = Category.objects.create(name="Романы", slug="novels")
        cls.product = Product.objects.create(
            category=genre,
            name="Война миров",
            slug="war-worlds",
            sku="TEST-BOOK-1",
            price=100,
        )
        cls.book = BookEdition.objects.create(
            product=cls.product,
            author="Герберт Уэллс",
            publisher="Heinemann",
            year=1898,
            language="Английский",
            binding="hardcover",
            pages=287,
        )
        cls.legacy = Product.objects.create(
            category=genre,
            name="Старый товар",
            slug="legacy-book-test",
            sku="TEST-LEGACY",
            price=100,
        )

    def test_isbn_validation(self):
        for valid in ("", "9780306406157", "9791090636071"):
            with self.subTest(valid=valid):
                self.book.isbn = valid
                self.book.full_clean()
        for invalid in ("9780306406158", "0000000000000", "9790000000001"):
            with self.subTest(invalid=invalid):
                self.book.isbn = invalid
                with self.assertRaises(ValidationError) as error:
                    self.book.full_clean()
                self.assertIn("isbn", error.exception.message_dict)

    def test_case_insensitive_author_and_title(self):
        for query in ("УЭЛЛС", "уэллс", "ВОЙНА МИРОВ", "война миров"):
            with self.subTest(query=query):
                response = self.client.get("/api/catalog/products/", {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([x["id"] for x in response.json()["results"]], [self.product.pk])

    def test_binding_filter(self):
        response = self.client.get("/api/catalog/products/", {"binding": "hardcover"})
        self.assertEqual([x["id"] for x in response.json()["results"]], [self.product.pk])
        self.assertEqual(response.json()["results"][0]["book"]["author"], "Герберт Уэллс")

    def test_legacy_product_has_null_book(self):
        response = self.client.get("/api/catalog/products/legacy-book-test/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["book"])

    def test_detail_has_ordered_gallery_and_list_keeps_its_contract(self):
        for position, label in ((2, "Задняя обложка"), (1, "Разворот")):
            ProductImage.objects.create(
                product=self.product,
                image=f"products/gallery/sample-{position}.jpg",
                alt_text=label,
                position=position,
            )
        detail = self.client.get("/api/catalog/products/war-worlds/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            [image["alt_text"] for image in detail.json()["images"]],
            ["Разворот", "Задняя обложка"],
        )
        listing = self.client.get("/api/catalog/products/")
        self.assertNotIn("images", listing.json()["results"][0])

    def test_stable_sort_with_equal_price(self):
        response = self.client.get("/api/catalog/products/", {"ordering": "price"})
        self.assertEqual(
            [x["id"] for x in response.json()["results"]], sorted([self.product.pk, self.legacy.pk])
        )

    def test_login(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(username="book_buyer", password="demo-password-123")
        response = APIClient().post(
            "/api/auth/token/", {"username": "book_buyer", "password": "demo-password-123"}
        )
        self.assertEqual(response.status_code, 200)

    def test_legacy_archive_is_preview_by_default_and_does_not_touch_changed_product(self):
        known = Product.objects.create(
            category=self.product.category,
            sku="DEMO-1",
            slug="demo-shirt-1",
            name="Демо-футболка 1",
            price=100,
        )
        changed = Product.objects.create(
            category=self.product.category,
            sku="DEMO-2",
            slug="demo-shirt-2",
            name="Своя книга",
            price=100,
        )
        csv_demo = Product.objects.create(
            category=self.product.category,
            sku="CSV-DEMO",
            slug="csv-demo",
            name="Демонстрационная книга",
            price=900,
        )
        preview = io.StringIO()
        call_command("archive_legacy_demo", stdout=preview)
        self.assertIn("CSV-DEMO: Демонстрационная книга", preview.getvalue())
        known.refresh_from_db()
        csv_demo.refresh_from_db()
        self.assertTrue(known.is_active)
        self.assertTrue(csv_demo.is_active)
        call_command("archive_legacy_demo", apply=True, stdout=io.StringIO())
        known.refresh_from_db()
        changed.refresh_from_db()
        csv_demo.refresh_from_db()
        self.assertFalse(known.is_active)
        self.assertFalse(csv_demo.is_active)
        self.assertTrue(changed.is_active)
