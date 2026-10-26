from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from catalog.admin import ProductImageInline
from catalog.filters import ProductFilter
from catalog.models import Product, ProductImage, Review
from catalog.templatetags.catalog_highlights import search_highlight
from catalog.tests.test_catalog import CatalogTestCase, User


class PriceValidationTests(CatalogTestCase):
    def test_clean_rejects_equal_and_lower_old_price(self):
        for value in ("500", "1000", "0"):
            with self.subTest(value=value):
                self.book.old_price = Decimal(value)
                with self.assertRaises(ValidationError) as error:
                    self.book.clean()
                self.assertIn("old_price", error.exception.message_dict)

    def test_clean_accepts_missing_or_higher_old_price(self):
        for value in (None, Decimal("1500")):
            self.book.old_price = value
            self.book.clean()

    def test_clean_tolerates_missing_price(self):
        self.book.price = None
        self.book.clean()

    def test_admin_change_form_returns_validation_error(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("admin:catalog_product_change", args=[self.book.pk]),
            {
                "category": self.books.pk,
                "name": self.book.name,
                "slug": self.book.slug,
                "sku": self.book.sku,
                "price": "1000",
                "old_price": "500",
                "stock": "0",
                "is_active": "on",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Старая цена должна быть больше текущей.")
        self.book.refresh_from_db()
        self.assertEqual(self.book.old_price, Decimal("1500"))

    def test_admin_list_editable_price_validation(self):
        model_admin = admin.site._registry[Product]
        request = RequestFactory().get("/admin/")
        request.user = self.user
        form = model_admin.get_changelist_formset(request).form
        bound = form(
            data={"price": "1600", "old_price": "1500", "stock": "0", "is_active": "on"},
            instance=self.book,
        )
        self.assertFalse(bound.is_valid())
        self.assertIn("old_price", bound.errors)


class HighlightTests(CatalogTestCase):
    def test_headline_uses_russian_morphology(self):
        product = Product.objects.search("ноутбуки").get(pk=self.laptop.pk)
        self.assertIn("<mark>Ноутбук</mark>", product.name_headline)
        self.assertIn("<mark>ноутбук</mark>", product.description_headline)

    def test_search_page_displays_highlights_without_extra_queries(self):
        with self.assertNumQueries(4):
            response = self.client.get(reverse("catalog:product_list"), {"q": "ноутбуки"})
        self.assertContains(response, "<mark>Ноутбук</mark>")
        self.assertContains(response, "<mark>ноутбук</mark>")

    def test_normal_catalog_does_not_highlight(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertNotContains(response, "<mark>")

    def test_search_escapes_malicious_product_content(self):
        self.laptop.name = 'Ноутбук <img src=x onerror="alert(1)">'
        self.laptop.description = (
            'Ноутбук <script>alert(1)</script> <mark onclick="evil()">test</mark>'
        )
        self.laptop.save()
        response = self.client.get(reverse("catalog:product_list"), {"q": "ноутбуки"})
        self.assertContains(response, "<mark>Ноутбук</mark>")
        self.assertNotContains(response, "<img src=x onerror=")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<mark onclick=")


class HighlightEscapingTests(SimpleTestCase):
    def test_only_plain_mark_tags_are_allowed(self):
        result = search_highlight(
            '<mark>word</mark><script>alert(1)</script><mark onclick="x">x</mark>'
        )
        self.assertIn("<mark>word</mark>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<mark onclick=", result)


class RatingFilterTests(CatalogTestCase):
    def setUp(self):
        second = User.objects.create_user("second")
        third = User.objects.create_user("third")
        Review.objects.create(product=self.laptop, author=self.user, rating=5, text="Good")
        Review.objects.create(product=self.laptop, author=second, rating=3, text="OK")
        Review.objects.create(
            product=self.laptop, author=third, rating=1, text="Hidden", is_published=False
        )
        Review.objects.create(product=self.book, author=self.user, rating=3, text="OK")

    def test_storefront_filters_average_inclusively(self):
        response = self.client.get(reverse("catalog:product_list"), {"rating_min": "4"})
        self.assertEqual(list(response.context["products"]), [self.laptop])
        self.assertContains(response, 'name="rating_min"')

    def test_api_uses_same_filter_and_ignores_hidden_reviews(self):
        response = APIClient().get("/api/catalog/products/", {"rating_min": "4"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], self.laptop.slug)
        self.assertEqual(response.data["results"][0]["rating"], 4)
        self.assertEqual(response.data["results"][0]["reviews_count"], 2)

    def test_unrated_products_are_excluded(self):
        Review.objects.all().delete()
        self.assertFalse(
            ProductFilter({"rating_min": "0"}, Product.objects.with_rating()).qs.exists()
        )

    def test_decimal_and_empty_thresholds(self):
        qs = Product.objects.active().with_rating()
        self.assertFalse(ProductFilter({"rating_min": "4.1"}, qs).qs.exists())
        self.assertEqual(ProductFilter({"rating_min": ""}, qs).qs.count(), 2)

    def test_invalid_api_threshold_returns_400(self):
        for value in ("abc", "-1", "6"):
            with self.subTest(value=value):
                response = APIClient().get("/api/catalog/products/", {"rating_min": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("rating_min", response.data)

    def test_combines_with_search_and_price(self):
        response = self.client.get(
            reverse("catalog:product_list"),
            {"rating_min": "4", "q": "ноутбуки", "price_max": "60000"},
        )
        self.assertEqual(list(response.context["products"]), [self.laptop])


class ProductImageTests(CatalogTestCase):
    def test_multiple_images_display_in_position_order(self):
        ProductImage.objects.create(product=self.laptop, image="gallery/second.png", position=2)
        ProductImage.objects.create(
            product=self.laptop, image="gallery/first.png", position=1, alt_text="Side view"
        )
        response = self.client.get(self.laptop.get_absolute_url())
        self.assertContains(response, "gallery/first.png")
        self.assertContains(response, "gallery/second.png")
        self.assertContains(response, 'alt="Side view"')
        body = response.content.decode()
        self.assertLess(body.index("gallery/first.png"), body.index("gallery/second.png"))

    def test_images_are_prefetched(self):
        for index in range(5):
            ProductImage.objects.create(product=self.laptop, image=f"gallery/{index}.png")
        with self.assertNumQueries(3):
            response = self.client.get(self.laptop.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_deleting_product_cascades_image_records(self):
        photo = ProductImage.objects.create(product=self.laptop, image="gallery/first.png")
        self.laptop.delete()
        self.assertFalse(ProductImage.objects.filter(pk=photo.pk).exists())

    def test_admin_has_tabular_inline(self):
        self.assertIn(ProductImageInline, admin.site._registry[Product].inlines)
        self.assertTrue(issubclass(ProductImageInline, admin.TabularInline))

    def test_inline_accepts_uploaded_image(self):
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (2, 2)).save(buffer, format="PNG")
        self.user.is_staff = self.user.is_superuser = True
        request = RequestFactory().get("/admin/")
        request.user = self.user
        inline = ProductImageInline(Product, admin.site)
        formset_class = inline.get_formset(request, self.laptop)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            formset = formset_class(
                data={
                    "images-TOTAL_FORMS": "1",
                    "images-INITIAL_FORMS": "0",
                    "images-0-alt_text": "Front",
                    "images-0-position": "0",
                },
                files={
                    "images-0-image": SimpleUploadedFile(
                        "front.png", buffer.getvalue(), "image/png"
                    )
                },
                instance=self.laptop,
            )
            self.assertTrue(formset.is_valid(), formset.errors)
            photo = formset.save()[0]
            self.assertTrue(photo.image.storage.exists(photo.image.name))
            self.assertEqual(photo.product, self.laptop)
