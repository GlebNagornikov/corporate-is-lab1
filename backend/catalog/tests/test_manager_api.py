import csv
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from catalog.caching import product_key
from catalog.models import BookEdition, Category, Product, ProductVariant

CATALOG = "/api/manager/catalog/"
CATEGORIES = "/api/manager/categories/"
STOREFRONT = "/api/catalog/products/"
CSV_IMPORT = f"{CATALOG}import-csv/"


def cover(image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (12, 18), "#472338").save(buffer, format=image_format)
    return SimpleUploadedFile("cover.png", buffer.getvalue(), "image/png")


class ManagerCatalogApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.buyer = users.create_user("buyer")
        cls.staff = users.create_user("staff", is_staff=True)
        cls.manager = users.create_user("manager")
        call_command("setup_groups", stdout=StringIO())
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))
        cls.root = Category.objects.create(name="Книги", slug="books")
        cls.genre = Category.objects.create(name="Проза", slug="fiction")
        cls.empty_genre = Category.objects.create(name="Детективы", slug="mystery")
        cls.legacy = Product.objects.create(
            category=cls.genre,
            name="Архив",
            sku="LEGACY",
            slug="archive",
            price=110,
            stock=1,
            is_active=False,
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.legacy,
            name="Склад",
            sku="STORE-LEGACY",
            price=110,
            stock=1,
        )

    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=folder))
        self.payload = {
            "category": self.genre.pk,
            "name": "Лес",
            "slug": "forest",
            "sku": "FOREST",
            "description": "Книжная аннотация",
            "price": "250.00",
            "stock": 3,
            "author": "Иван Петров",
            "publisher": "Полка",
            "year": 2025,
            "language": "Русский",
            "binding": "hardcover",
            "isbn": "9780140449136",
            "pages": 320,
        }

    def create_book(self, **values):
        self.client.force_authenticate(self.manager)
        response = self.client.post(CATALOG, {**self.payload, **values}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def upload_csv(self, rows, *, delimiter=",", **form):
        stream = StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
        file = SimpleUploadedFile("books.csv", stream.getvalue().encode("utf-8-sig"), "text/csv")
        self.client.force_authenticate(self.manager)
        return self.client.post(CSV_IMPORT, {"file": file, **form}, format="multipart")

    def test_all_manager_catalog_methods_require_authentication(self):
        detail = f"{CATALOG}{self.legacy.pk}/"
        endpoints = [
            ("get", CATALOG),
            ("post", CATALOG),
            ("get", detail),
            ("patch", detail),
            ("delete", detail),
            ("patch", f"{detail}variants/{self.variant.pk}/"),
            ("post", CSV_IMPORT),
            ("get", CATEGORIES),
            ("post", CATEGORIES),
        ]
        for user, expected in [(None, 401), (self.buyer, 403), (self.staff, 403)]:
            self.client.force_authenticate(user)
            for method, url in endpoints:
                with self.subTest(expected=expected, method=method, url=url):
                    self.assertEqual(getattr(self.client, method)(url).status_code, expected)

    def test_read_only_catalog_permissions_cannot_create_or_edit(self):
        for app, code in (
            ("orders", "change_order"),
            ("catalog", "view_product"),
            ("catalog", "view_category"),
        ):
            self.staff.user_permissions.add(
                Permission.objects.get(content_type__app_label=app, codename=code)
            )
        self.client.force_authenticate(self.staff)
        self.assertTrue(self.client.get("/api/auth/me/").data["is_manager"])
        self.assertEqual(self.client.get(CATALOG).status_code, 200)
        self.assertEqual(self.client.post(CATALOG, self.payload).status_code, 403)
        self.assertEqual(self.client.patch(f"{CATALOG}{self.legacy.pk}/").status_code, 403)
        self.assertEqual(self.client.delete(f"{CATALOG}{self.legacy.pk}/").status_code, 403)
        self.assertEqual(self.client.post(CSV_IMPORT).status_code, 403)
        variant_url = f"{CATALOG}{self.legacy.pk}/variants/{self.variant.pk}/"
        self.assertEqual(self.client.patch(variant_url).status_code, 403)
        self.assertEqual(self.client.get("/api/manager/orders/").status_code, 403)
        self.assertEqual(self.client.post(CATEGORIES, {"name": "История"}).status_code, 403)

    def test_categories_include_genres_without_visible_books(self):
        self.client.force_authenticate(self.manager)
        ids = {row["id"] for row in self.client.get(CATEGORIES).data}
        self.assertIn(self.empty_genre.pk, ids)
        self.assertNotIn(self.root.pk, ids)

    def test_manager_creates_genre_under_books_and_can_use_it_immediately(self):
        self.client.force_authenticate(self.manager)
        genre = self.client.post(CATEGORIES, {"name": "  Исторический роман  "})
        self.assertEqual(genre.status_code, 201, genre.data)
        self.assertEqual(genre.data["parent"], "books")
        self.assertEqual(genre.data["name"], "Исторический роман")
        self.assertIn(genre.data, self.client.get(CATEGORIES).data)
        duplicate = self.client.post(CATEGORIES, {"name": "исторический роман"})
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("name", duplicate.data)
        book = self.create_book(category=genre.data["id"], is_active="true")
        public = self.client.get(STOREFRONT, {"category": genre.data["slug"]})
        self.assertEqual([row["id"] for row in public.data["results"]], [book["id"]])

    def test_book_cannot_be_assigned_to_books_root(self):
        self.client.force_authenticate(self.manager)
        payload = {**self.payload, "category": self.root.pk}
        response = self.client.post(CATALOG, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)
        book = self.create_book()
        response = self.client.patch(f"{CATALOG}{book['id']}/", {"category": self.root.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)

    def test_isbn_with_separators_is_saved_as_thirteen_digits(self):
        book = self.create_book(isbn="978–0 14-044913-6")
        self.assertEqual(book["book"]["isbn"], "9780140449136")
        url = f"{CATALOG}{book['id']}/"
        invalid = self.client.patch(url, {"isbn": "978-5-17-1542"}, format="multipart")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("isbn", invalid.data)
        self.assertEqual(self.client.get(url).data["book"]["isbn"], "9780140449136")

    def test_catalog_searches_author_case_insensitively_and_includes_drafts(self):
        draft = self.create_book()
        result = self.client.get(CATALOG, {"q": "ИВАН пЕТРОВ"})
        self.assertEqual([row["id"] for row in result.data["results"]], [draft["id"]])
        self.assertFalse(result.data["results"][0]["is_active"])
        self.assertEqual(self.client.get(f"{STOREFRONT}forest/").status_code, 404)

    def test_catalog_pagination_has_no_duplicate_rows(self):
        Product.objects.bulk_create(
            Product(category=self.genre, name=f"Книга {i}", slug=f"book-{i}", sku=f"B-{i}", price=1)
            for i in range(21)
        )
        self.client.force_authenticate(self.manager)
        first = self.client.get(CATALOG).data
        second = self.client.get(CATALOG, {"page": 2}).data
        self.assertEqual(first["count"], 22)
        self.assertTrue(first["next"])
        self.assertTrue(second["previous"])
        self.assertEqual(len({row["id"] for row in first["results"] + second["results"]}), 22)

    def test_delete_unused_book_removes_public_and_manager_cards(self):
        book = self.create_book(is_active="true")
        url = f"{CATALOG}{book['id']}/"
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"{STOREFRONT}forest/").status_code, 404)
        self.assertFalse(BookEdition.objects.filter(product_id=book["id"]).exists())

    def test_csv_preview_and_import_create_books_and_update_by_sku(self):
        first = {**self.payload, "category": self.genre.slug, "isbn": "978-0-14-044913-6"}
        second = {**first, "sku": "LAKE", "slug": "lake", "name": "Озеро"}
        preview = self.upload_csv([first, second], delimiter=";")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data, {"processed": 2, "dry_run": True})
        self.assertFalse(Product.objects.filter(sku="FOREST").exists())
        applied = self.upload_csv([first, second], delimiter=";", dry_run="false")
        self.assertEqual(applied.status_code, 200, applied.data)
        self.assertEqual(applied.data, {"processed": 2, "dry_run": False})
        book = Product.objects.get(sku="FOREST")
        self.assertEqual(book.book.isbn, "9780140449136")
        self.assertFalse(book.is_active)
        updated = self.upload_csv([{"sku": "FOREST", "stock": 12}], dry_run="false")
        self.assertEqual(updated.status_code, 200, updated.data)
        book.refresh_from_db()
        self.assertEqual(
            (book.slug, book.stock, book.book.author), ("forest", 12, self.payload["author"])
        )
        self.assertTrue(Product.objects.filter(sku="LAKE").exists())

    def test_csv_import_reports_row_errors_and_rejects_whole_file(self):
        first = {**self.payload, "category": self.genre.slug}
        invalid = {**first, "sku": "OTHER", "slug": "other", "year": "bad"}
        response = self.upload_csv([first, invalid], dry_run="false")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("Строка 3, year", response.data["file"][0])
        self.assertFalse(Product.objects.filter(sku__in=["FOREST", "OTHER"]).exists())

    def test_editorial_keeps_oz_after_newer_books_fill_the_first_page(self):
        oz = Product.objects.create(
            category=self.genre,
            slug="wonderful-wizard-oz-1900",
            sku="OZ",
            name="Страна Оз",
            price=1,
        )
        Product.objects.bulk_create(
            Product(category=self.genre, slug=f"new-{i}", sku=f"N-{i}", name=f"Новая {i}", price=1)
            for i in range(21)
        )
        first = self.client.get(STOREFRONT).data["results"]
        self.assertNotIn(oz.pk, [book["id"] for book in first])
        selection = self.client.get("/api/catalog/editorial/")
        self.assertEqual(selection.status_code, 200, selection.data)
        self.assertEqual([book["id"] for book in selection.data], [oz.pk])
        oz.is_active = False
        oz.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/catalog/editorial/").data, [])

    def test_create_uploads_cover_and_keeps_book_metadata(self):
        book = self.create_book(image=cover())
        self.assertEqual(book["book"]["isbn"], self.payload["isbn"])
        saved = Product.objects.get(pk=book["id"])
        self.assertTrue(saved.image.storage.exists(saved.image.name))
        self.assertTrue(saved.image.name.endswith(".png"))
        self.assertFalse(book["is_active"])

    def test_publish_edit_and_unpublish_refresh_storefront_and_keep_cover(self):
        book = self.create_book(image=cover("JPEG"))
        url = f"{CATALOG}{book['id']}/"
        before = product_key("forest")
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.patch(
                url, {"price": "280.00", "stock": 4, "is_active": "true"}, format="multipart"
            )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["image"], book["image"])
        self.assertTrue(result.data["image"].endswith(".jpg"))
        self.assertNotEqual(before, product_key("forest"))
        visible = self.client.get(f"{STOREFRONT}forest/")
        self.assertEqual(visible.status_code, 200)
        self.assertEqual((visible.data["price"], visible.data["stock"]), ("280.00", 4))
        self.assertEqual(self.client.patch(url, {"is_active": False}).status_code, 200)
        self.assertEqual(self.client.get(f"{STOREFRONT}forest/").status_code, 404)

    def test_invalid_cover_has_field_error_and_rolls_back_other_changes(self):
        book = self.create_book(image=cover())
        url = f"{CATALOG}{book['id']}/"
        for invalid in (
            SimpleUploadedFile("fake.png", b"not an image", "image/png"),
            SimpleUploadedFile("large.png", b"0" * (5 * 1024 * 1024 + 1), "image/png"),
            cover("GIF"),
        ):
            with self.subTest(file=invalid.name):
                response = self.client.patch(
                    url, {"name": "Изменено", "image": invalid}, format="multipart"
                )
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("image", response.data)
        detail = self.client.get(url).data
        self.assertEqual((detail["name"], detail["image"]), (book["name"], book["image"]))

    def test_invalid_book_fields_and_duplicate_identifiers_return_field_errors(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            CATALOG,
            {**self.payload, "isbn": "9780140449137", "old_price": "199.00"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(set(response.data), {"isbn", "old_price"})
        self.assertFalse(BookEdition.objects.exists())
        self.create_book()
        duplicate = self.client.post(CATALOG, self.payload, format="multipart")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(set(duplicate.data), {"slug", "sku"})

    def test_legacy_card_can_receive_book_metadata_with_unchanged_identity(self):
        self.client.force_authenticate(self.manager)
        url = f"{CATALOG}{self.legacy.pk}/"
        self.assertIsNone(self.client.get(url).data["book"])
        fields = {
            key: self.payload[key]
            for key in (
                "author",
                "publisher",
                "year",
                "language",
                "binding",
                "isbn",
                "pages",
            )
        }
        changed = self.client.patch(url, {**fields, "sku": "DIFFERENT"}, format="multipart")
        self.assertEqual(changed.status_code, 400)
        self.assertIn("sku", changed.data)
        response = self.client.patch(url, fields, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sku"], "LEGACY")
        self.assertEqual(response.data["book"]["author"], self.payload["author"])

    def test_stock_and_price_remain_linked_to_default_variant(self):
        book = self.create_book()
        variant = ProductVariant.objects.create(
            product_id=book["id"],
            name="Стандартный",
            sku="DEFAULT",
            price=book["price"],
            stock=book["stock"],
            is_default=True,
        )
        changed = self.client.patch(f"{CATALOG}{book['id']}/", {"price": "280.00", "stock": 5})
        self.assertEqual(changed.status_code, 200, changed.data)
        variant.refresh_from_db()
        self.assertEqual((str(variant.price), variant.stock), ("280.00", 5))

    def test_variant_updates_aggregate_inventory_and_cannot_target_another_book(self):
        book = self.create_book()
        detail = f"{CATALOG}{self.legacy.pk}/"
        direct = self.client.patch(detail, {"stock": 6})
        self.assertEqual(direct.status_code, 400)
        self.assertIn("stock", direct.data)
        wrong_book = f"{CATALOG}{book['id']}/variants/{self.variant.pk}/"
        self.assertEqual(self.client.patch(wrong_book, {"stock": 6}).status_code, 404)
        url = f"{detail}variants/{self.variant.pk}/"
        result = self.client.patch(url, {"stock": 6, "price": "900.00"})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual((result.data["stock"], result.data["price"]), (6, "900.00"))
        disabled = self.client.patch(url, {"is_active": False})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.data["stock"], 0)
        self.assertEqual(self.client.get(f"{CATALOG}999999/").status_code, 404)
