import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from catalog.models import BookEdition, Category, Product
from orders.models import Order, OrderItem
from orders.reporting import sales_report


class ReportTests(APITestCase):
    json_url = "/api/manager/reports/sales/"
    csv_url = "/api/manager/reports/sales/csv/"

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

    def authenticate(self, *codenames):
        self.user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="orders", codename__in=codenames)
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}")

    def test_api_reports_require_authentication_manager_role_and_view_permission(self):
        day = timezone.localdate().isoformat()
        for permissions, expected in [
            (None, 401),
            ((), 403),
            (("view_order",), 403),
            (("change_order",), 403),
            (("change_order", "view_order"), 200),
        ]:
            self.user.user_permissions.clear()
            if permissions is not None:
                self.authenticate(*permissions)
            for url in (self.json_url, self.csv_url):
                with self.subTest(url=url, permissions=permissions):
                    response = self.client.get(url, {"start": day, "end": day})
                    self.assertEqual(response.status_code, expected)

    def test_api_reports_validate_both_dates_and_return_empty_period(self):
        self.authenticate("change_order", "view_order")
        for url in (self.json_url, self.csv_url):
            for invalid in (
                {"start": "2024-02-29"},
                {"start": "2026-02-29", "end": "2026-03-01"},
                {"start": "2026-03-02", "end": "2026-03-01"},
            ):
                with self.subTest(url=url, invalid=invalid):
                    response = self.client.get(url, invalid)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response["Content-Type"], "application/json")

        period = {"start": "2000-01-01", "end": "2000-01-01"}
        report = self.client.get(self.json_url, period).json()
        self.assertEqual(report["summary"], {"count": 0, "revenue": "0.00", "average": "0.00"})
        self.assertEqual(report["daily"], [])
        self.assertEqual(report["statuses"], [])
        self.assertEqual(report["top_quantity"], [])
        self.assertContains(self.client.get(self.csv_url, period), "Итого,Число заказов,0")

    def test_api_json_and_csv_match_local_day_and_protect_spreadsheet_cells(self):
        self.authenticate("change_order", "view_order")
        day = date(2026, 11, 10)
        midnight = timezone.make_aware(datetime.combine(day, time.min))
        Order.objects.update(created_at=midnight)
        outside = Order.objects.create(
            user=self.user, subtotal=500, total=500, email="b@example.test"
        )
        Order.objects.filter(pk=outside.pk).update(created_at=midnight - timedelta(seconds=1))
        OrderItem.objects.update(product_name=" =2+2")
        BookEdition.objects.create(
            product=self.product,
            author="Author",
            publisher="Publisher",
            year=2000,
            language="Русский",
            binding=BookEdition.Binding.HARDCOVER,
            pages=100,
        )
        historical = Product.objects.create(
            category=self.product.category, name="Old product", slug="old", sku="old", price=20
        )
        OrderItem.objects.create(
            order=Order.objects.exclude(pk=outside.pk).first(),
            product=historical,
            product_name=historical.name,
            price=20,
            quantity=100,
        )

        period = {"start": day.isoformat(), "end": day.isoformat()}
        report = self.client.get(self.json_url, period).json()
        response = self.client.get(self.csv_url, period, HTTP_ACCEPT="text/csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        rows = list(csv.reader(response.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(report["summary"], {"count": 2, "revenue": "60.00", "average": "30.00"})
        self.assertEqual(
            report["daily"], [{"day": day.isoformat(), "count": 2, "revenue": "60.00"}]
        )
        for status in report["statuses"]:
            self.assertIn(["По статусам", status["label"], str(status["count"]), ""], rows)
        self.assertIn(["По дням", day.isoformat(), "2", "60.00"], rows)
        book = report["top_quantity"][0]
        self.assertEqual(len(report["top_quantity"]), 1)
        self.assertEqual((book["name"], book["quantity"], book["revenue"]), (" =2+2", 4, "40.00"))
        self.assertIn(["Лидеры по количеству", "' =2+2", "4", "40.00"], rows)
        self.assertNotIn(historical.name, response.content.decode("utf-8-sig"))
