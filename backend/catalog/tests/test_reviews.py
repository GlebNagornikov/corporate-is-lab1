from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import connections
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from catalog.models import Category, Product, Review
from catalog.reviews import review_block_reason
from orders.models import Order, OrderItem

User = get_user_model()
QUEUE_URL = "/api/manager/reviews/"
PAYLOAD = {"rating": 5, "text": "Хорошая книга"}


def add_purchase(user, product, status=Order.Status.DELIVERED):
    order = Order.objects.create(
        user=user,
        status=status,
        subtotal=product.price,
        total=product.price,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        price=product.price,
        quantity=1,
    )
    return order


def add_book(sku):
    category, _ = Category.objects.get_or_create(slug="books", defaults={"name": "Книги"})
    return Product.objects.create(category=category, name=sku, sku=sku, slug=sku, price="10.00")


class ReviewApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = add_book("book-one")
        cls.buyer = User.objects.create_user("buyer")
        cls.other = User.objects.create_user("other")
        cls.manager = User.objects.create_user("manager")
        call_command("setup_groups", verbosity=0)
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))
        cls.detail = f"/api/catalog/products/{cls.book.slug}/"
        cls.reviews = f"{cls.detail}reviews/"
        cls.eligibility = f"{cls.detail}review-eligibility/"

    def test_guest_and_own_delivered_purchase_are_distinguished(self):
        self.assertEqual(self.client.get(self.eligibility).status_code, 401)
        self.assertEqual(self.client.post(self.reviews, PAYLOAD).status_code, 401)
        self.assertNotIn("can_review", self.client.get(self.detail).data)
        add_purchase(self.other, self.book)
        add_purchase(self.buyer, add_book("book-two"))
        order = add_purchase(self.buyer, self.book, Order.Status.SHIPPED)
        self.client.force_authenticate(self.buyer)
        response = self.client.get(self.eligibility)
        self.assertFalse(response.data["can_review"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        response = self.client.post(self.reviews, PAYLOAD)
        self.assertEqual(response.status_code, 400)
        self.assertIn("после доставки", response.data["detail"])
        self.assertFalse(Review.objects.exists())
        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])
        self.assertTrue(self.client.get(self.eligibility).data["can_review"])

    def test_review_is_pending_even_when_request_tries_to_publish_it(self):
        add_purchase(self.buyer, self.book)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(self.reviews, {**PAYLOAD, "status": "approved"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.get().status, Review.Status.PENDING)
        self.assertFalse(self.client.get(self.eligibility).data["can_review"])
        self.assertIn("ожидает", self.client.get(self.eligibility).data["message"])
        self.assertEqual(self.client.post(self.reviews, PAYLOAD).status_code, 400)
        self.assertEqual(self.client.get(self.reviews).data["results"], [])
        self.assertIsNone(self.client.get(self.detail).data["rating"])

        self.client.force_authenticate(self.other)
        self.assertIn("после доставки", self.client.get(self.eligibility).data["message"])

    def test_legacy_form_enforces_purchase_and_cannot_bypass_duplicate_rule(self):
        self.client.force_login(self.buyer)
        url = reverse("catalog:review_create", args=[self.book.slug])
        response = self.client.post(url, PAYLOAD, follow=True)
        self.assertContains(response, "после доставки")
        self.assertFalse(Review.objects.exists())
        add_purchase(self.buyer, self.book)
        self.assertTrue(self.client.get(self.book.get_absolute_url()).context["can_review"])
        self.client.post(url, PAYLOAD)
        self.client.post(url, PAYLOAD)
        self.assertEqual(Review.objects.get().status, Review.Status.PENDING)
        self.assertFalse(self.client.get(self.book.get_absolute_url()).context["can_review"])

    def test_public_pagination_only_includes_approved_reviews_in_stable_order(self):
        approved = [
            Review.objects.create(
                product=self.book,
                author=User.objects.create_user(f"reader{i}"),
                status=Review.Status.APPROVED,
                **PAYLOAD,
            )
            for i in range(6)
        ]
        Review.objects.filter(pk__in=[review.pk for review in approved]).update(
            created_at=approved[0].created_at
        )
        Review.objects.create(product=self.book, author=self.buyer, **PAYLOAD)
        Review.objects.create(
            product=self.book, author=self.other, status=Review.Status.REJECTED, **PAYLOAD
        )
        first = self.client.get(self.reviews).data
        self.assertEqual(first["count"], 6)
        self.assertIsNotNone(first["next"])
        second = self.client.get(self.reviews, {"page": 2}).data
        self.assertIsNone(second["next"])
        self.assertEqual(
            [row["id"] for row in first["results"] + second["results"]],
            [review.pk for review in reversed(approved)],
        )

    def test_manager_approval_updates_rating_and_rejection_stays_private(self):
        approved = Review.objects.create(product=self.book, author=self.buyer, **PAYLOAD)
        rejected = Review.objects.create(product=self.book, author=self.other, **PAYLOAD)
        legacy_url = self.book.get_absolute_url()
        self.assertIsNone(self.client.get(legacy_url).context["product"].rating)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get(QUEUE_URL).data["count"], 2)
        for review, decision in ((approved, "approved"), (rejected, "rejected")):
            response = self.client.post(f"{QUEUE_URL}{review.pk}/moderate/", {"decision": decision})
            self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(QUEUE_URL).data["results"], [])
        self.assertEqual(self.client.get(self.detail).data["rating"], 5)
        self.assertEqual(self.client.get(legacy_url).context["product"].reviews_count, 1)
        self.assertEqual(
            [row["id"] for row in self.client.get(self.reviews).data["results"]], [approved.pk]
        )
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, Review.Status.REJECTED)
        self.assertEqual(
            self.client.post(
                f"{QUEUE_URL}{approved.pk}/moderate/", {"decision": "rejected"}
            ).status_code,
            400,
        )
        self.client.force_authenticate(self.other)
        self.assertFalse(self.client.get(self.eligibility).data["can_review"])
        self.assertEqual(self.client.post(self.reviews, PAYLOAD).status_code, 400)

    def test_manager_endpoints_require_auth_and_model_permissions(self):
        review = Review.objects.create(product=self.book, author=self.buyer, **PAYLOAD)
        decision_url = f"{QUEUE_URL}{review.pk}/moderate/"
        self.assertEqual(self.client.get(QUEUE_URL).status_code, 401)
        self.assertEqual(self.client.post(decision_url, {"decision": "approved"}).status_code, 401)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(QUEUE_URL).status_code, 403)
        self.assertEqual(self.client.post(decision_url, {"decision": "approved"}).status_code, 403)
        reader = User.objects.create_user("review_reader")
        reader.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["change_order", "view_review"],
                content_type__app_label__in=["orders", "catalog"],
            )
        )
        self.client.force_authenticate(reader)
        self.assertEqual(self.client.get(QUEUE_URL).status_code, 200)
        self.assertEqual(self.client.post(decision_url, {"decision": "approved"}).status_code, 403)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post(decision_url, {"decision": "pending"}).status_code, 400)
        self.assertEqual(
            self.client.post(f"{QUEUE_URL}9999/moderate/", {"decision": "approved"}).status_code,
            404,
        )
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.PENDING)


class ConcurrentReviewApiTests(APITransactionTestCase):
    def test_concurrent_requests_create_only_one_review(self):
        book = add_book("concurrent-book")
        buyer = User.objects.create_user("concurrent_buyer")
        add_purchase(buyer, book)
        checked = Barrier(2)

        def check(product, user):
            reason = review_block_reason(product, user)
            checked.wait(timeout=10)
            return reason

        def post():
            try:
                client = APIClient()
                client.force_authenticate(buyer)
                return client.post(
                    f"/api/catalog/products/{book.slug}/reviews/", PAYLOAD
                ).status_code
            finally:
                connections.close_all()

        with (
            patch("catalog.reviews.review_block_reason", side_effect=check),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            statuses = list(pool.map(lambda _: post(), range(2)))
        self.assertCountEqual(statuses, [201, 400])
        self.assertEqual(Review.objects.get().status, Review.Status.PENDING)
