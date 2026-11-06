from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from catalog.models import Category, Product
from orders.models import Order, OrderItem
from orders.reporting import sales_report


class ReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("reports")
        self.product = Product.objects.create(
            category=Category.objects.create(name="Books", slug="books"),
            name="Book",
            slug="book",
            sku="book",
            price=10,
        )
        for status, total in [("new", 25), ("paid", 35), ("cancelled", 1000)]:
            order = Order.objects.create(
                user=self.user,
                status=status,
                full_name="Buyer",
                phone="1",
                email="b@example.test",
                subtotal=total,
                total=total,
            )
            OrderItem.objects.create(
                order=order, product=self.product, product_name="Book", price=10, quantity=2
            )

    def test_totals_exclude_cancelled_and_top_aggregates(self):
        report = sales_report()
        self.assertEqual(
            report["summary"], {"count": 2, "revenue": Decimal("60"), "average": Decimal("30")}
        )
        self.assertEqual(report["top_quantity"][0]["quantity"], 4)
        self.assertEqual(report["top_revenue"][0]["revenue"], 40)
        self.assertEqual(len(report["statuses"]), 3)

    def test_query_count_is_constant_and_period_filters(self):
        with self.assertNumQueries(6):
            sales_report()
        Order.objects.bulk_create(
            [
                Order(
                    user=self.user,
                    full_name="X",
                    phone="1",
                    email="x@example.test",
                    subtotal=1,
                    total=1,
                )
                for _ in range(30)
            ]
        )
        with self.assertNumQueries(6):
            sales_report()
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertEqual(sales_report(start=tomorrow)["summary"]["count"], 0)
        self.assertEqual(sales_report(end=date(2000, 1, 1))["summary"]["revenue"], 0)

    def test_permission_csv_and_bad_period(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/reports/sales/").status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename="view_order"))
        response = self.client.get("/reports/sales/?format=csv")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Итого,Выручка,60")
        self.assertContains(response, "По статусам,Отменён,1")
        self.assertContains(response, "По способам доставки,Самовывоз,2")
        report = self.client.get("/reports/sales/")
        self.assertContains(report, "Отменён — 1")
        self.assertContains(report, "Оплачен — 1")
        self.assertContains(report, "Самовывоз — 2")
        self.assertNotContains(report, "cancelled")
        self.assertNotContains(report, "pickup")
        self.assertContains(
            self.client.get("/reports/sales/?start=2026-11-04&end=2020-01-01"),
            "Начало периода позже окончания",
        )

    def test_manager_can_open_report_from_orders_admin(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename="view_order"))
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/admin/orders/order/"), 'href="/reports/sales/"')
