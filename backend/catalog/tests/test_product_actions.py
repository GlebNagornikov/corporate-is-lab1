from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parents = []
        self.forms = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms[attrs.get("action")] = list(self.parents)
        if tag not in {"input", "img", "meta", "link", "br", "hr"}:
            self.parents.append((tag, attrs.get("class", "")))

    def handle_endtag(self, tag):
        if self.parents and self.parents[-1][0] == tag:
            self.parents.pop()


class ProductActionTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Category.objects.create(name="Книги", slug="books"),
            name="Книга",
            slug="book",
            sku="book",
            price=100,
            stock=5,
        )
        self.user = get_user_model().objects.create_user("actions")
        self.client.force_login(self.user)

    def test_actions_return_to_catalog_with_filters_or_product(self):
        for endpoint in ("wishlist", "compare"):
            for next_url in ("/?category=books&page=2", self.product.get_absolute_url()):
                response = self.client.post(f"/{endpoint}/{self.product.pk}/", {"next": next_url})
                self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertEqual(self.user.wishlist.count(), 1)
        self.assertEqual(self.client.session["comparison"], [self.product.pk])

    def test_actions_reject_external_next_and_keep_legacy_fallback(self):
        for endpoint, fallback in (("wishlist", "/wishlist/"), ("compare", "/compare/")):
            for next_url in ("https://example.test/", "//example.test/", ""):
                response = self.client.post(f"/{endpoint}/{self.product.pk}/", {"next": next_url})
                self.assertRedirects(response, fallback)

    def test_actions_are_inside_card_and_detail_content(self):
        for url in ("/", self.product.get_absolute_url()):
            response = self.client.get(url)
            parser = FormParser()
            parser.feed(response.content.decode())
            for endpoint in ("wishlist", "compare"):
                parents = parser.forms[f"/{endpoint}/{self.product.pk}/"]
                self.assertTrue(any(tag == "main" for tag, _ in parents))
                self.assertFalse(any(tag == "title" for tag, _ in parents))
                if url == "/":
                    self.assertTrue(any("card-body" in classes.split() for _, classes in parents))
