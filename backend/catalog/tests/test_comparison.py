from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.comparison import add_comparison, comparison_rows
from catalog.models import Category, Product


class ComparisonTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books", slug="books")
        self.products = [
            Product.objects.create(
                category=self.category,
                name=f"Book {i}",
                slug=f"book-{i}",
                sku=f"b{i}",
                price=10 + i,
                attributes={"Pages": i},
            )
            for i in range(5)
        ]

    def test_limit_and_duplicate(self):
        session = {}
        for product in self.products[:4]:
            add_comparison(session, product)
        add_comparison(session, self.products[0])
        self.assertEqual(len(session["comparison"]), 4)
        with self.assertRaises(ValidationError):
            add_comparison(session, self.products[4])

    def test_other_root_rejected_child_allowed(self):
        session = {}
        add_comparison(session, self.products[0])
        child = Category.objects.create(name="Child", slug="child", parent=self.category)
        self.products[1].category = child
        self.products[1].save()
        add_comparison(session, self.products[1])
        self.products[2].category = Category.objects.create(name="Other", slug="other")
        self.products[2].save()
        with self.assertRaises(ValidationError):
            add_comparison(session, self.products[2])

    def test_guest_session_and_differences(self):
        for product in self.products[:2]:
            self.client.post(f"/compare/{product.pk}/")
        response = self.client.get("/compare/")
        self.assertContains(response, "table-warning")
        self.assertTrue(
            next(row for row in comparison_rows(response.context["products"]) if row[0] == "Pages")[
                2
            ]
        )
        self.client.post(f"/compare/{self.products[0].pk}/", {"action": "remove"})
        self.assertEqual(len(self.client.session["comparison"]), 1)
