from decimal import Decimal
from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from cart.models import Cart
from cart.services import add_to_cart
from catalog.models import Category, Product
from orders.management.commands.setup_groups import GROUPS
from orders.models import Order
from orders.services import place_order

User = get_user_model()


class ManagerAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_groups", stdout=StringIO())
        cls.manager = User.objects.create_user("manager", password="pass12345", is_staff=True)
        cls.manager.groups.add(Group.objects.get(name="Менеджеры магазина"))
        cls.buyer = User.objects.create_user("buyer", password="pass12345")
        cls.superuser = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        category = Category.objects.create(name="Книги", slug="books")
        cls.product = Product.objects.create(
            category=category,
            name="Книга",
            slug="book",
            sku="BK-1",
            price=Decimal("1000"),
            stock=5,
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def make_order(self):
        cart = Cart.objects.create(user=self.buyer)
        add_to_cart(cart, self.product, 1)
        return place_order(
            user=self.buyer,
            cart=cart,
            full_name="Покупатель",
            phone="1",
            email="buyer@example.com",
            delivery_method="pickup",
        )

    def test_setup_groups_is_idempotent_and_replaces_permissions(self):
        group = Group.objects.get(name="Менеджеры магазина")
        group.permissions.add(Permission.objects.get(codename="delete_order"))
        for _ in range(2):
            call_command("setup_groups", stdout=StringIO())
        actual = {
            f"{permission.content_type.app_label}.{permission.codename}"
            for permission in group.permissions.select_related("content_type")
        }
        self.assertEqual(actual, set(GROUPS[group.name]))
        self.assertEqual(group.permissions.count(), 12)

    def test_manager_index_shows_only_allowed_models(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        models = {
            model["object_name"] for app in response.context["app_list"] for model in app["models"]
        }
        self.assertEqual(models, {"Order", "PromoCode", "Category", "Product", "Review"})
        self.assertContains(self.client.get(reverse("catalog:product_list")), "Панель менеджера")
        for name in ["employees_employee", "employees_department", "accounts_user", "cart_cart"]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(f"admin:{name}_changelist")).status_code, 403
                )

    def test_order_fields_and_inlines_are_readonly(self):
        order = self.make_order()
        response = self.client.get(reverse("admin:orders_order_change", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        fields = response.context["adminform"].form.fields
        for name in [
            "user",
            "status",
            "promo_code",
            "subtotal",
            "discount",
            "delivery_cost",
            "total",
        ]:
            self.assertNotIn(name, fields)
        self.assertFalse(response.context["has_delete_permission"])
        for inline in response.context["inline_admin_formsets"]:
            self.assertFalse(inline.has_add_permission)
            self.assertFalse(inline.has_delete_permission)
            self.assertFalse(inline.has_change_permission)

    def test_order_creation_and_deletion_are_forbidden_even_for_superuser(self):
        order = self.make_order()
        for user in [self.manager, self.superuser]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("admin:orders_order_add")).status_code, 403)
            url = reverse("admin:orders_order_delete", args=[order.pk])
            self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
            request = RequestFactory().get("/admin/orders/order/")
            request.user = user
            self.assertNotIn("delete_selected", admin.site._registry[Order].get_actions(request))
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_admin_actions_validate_workflow_and_send_email(self):
        order = self.make_order()
        url = reverse("admin:orders_order_changelist")
        response = self.client.post(
            url, {"action": "mark_delivered", "_selected_action": [order.pk]}, follow=True
        )
        self.assertContains(response, "нельзя перейти")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.history.count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                url, {"action": "mark_confirmed", "_selected_action": [order.pk]}, follow=True
            )
        self.assertContains(response, "Обновлено заказов: 1")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        entry = order.history.latest("created_at")
        self.assertEqual(entry.changed_by, self.manager)
        self.assertEqual(entry.comment, "Через панель менеджера")
        self.assertEqual(len(mail.outbox), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"action": "mark_cancelled", "_selected_action": [order.pk]})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_manager_can_add_promo_but_cannot_delete_it(self):
        response = self.client.get(reverse("admin:orders_promocode_add"))
        self.assertEqual(response.status_code, 200)
        request = RequestFactory().get("/admin/orders/promocode/")
        request.user = self.manager
        from orders.models import PromoCode

        modeladmin = admin.site._registry[PromoCode]
        self.assertTrue(modeladmin.has_add_permission(request))
        self.assertTrue(modeladmin.has_change_permission(request))
        self.assertFalse(modeladmin.has_delete_permission(request))
