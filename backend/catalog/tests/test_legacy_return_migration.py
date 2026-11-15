from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from catalog.models import Product, ProductVariant
from orders.models import Order


class LegacyReturnMigrationTests(TransactionTestCase):
    def test_existing_orders_can_be_cancelled_after_catalog_upgrade(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_catalog = ("catalog", "0012_restocknotification")
        targets = [old_catalog, *(node for node in latest if node[0] != "catalog")]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        executor.migrate(targets)
        old = executor.loader.project_state(targets).apps

        category = old.get_model("catalog", "Category").objects.create(name="Книги", slug="books")
        book = old.get_model("catalog", "Product").objects.create(
            category=category,
            name="Existing book",
            sku="OLD",
            slug="existing-book",
            price=Decimal("20.00"),
            stock=3,
        )
        variants = old.get_model("catalog", "ProductVariant").objects
        default = variants.create(
            product=book, name="Standard", sku="OLD-STD", price=10, is_default=True
        )
        warehouse = variants.create(product=book, name="Warehouse", sku="OLD-WH", price=20, stock=3)
        user_app, user_model = get_user_model()._meta.label.split(".")
        buyer = old.get_model(user_app, user_model).objects.create(username="existing-buyer")
        order_ids = []
        for variant in (None, default):
            order = old.get_model("orders", "Order").objects.create(
                user=buyer,
                full_name="Existing buyer",
                phone="+79135551234",
                email="buyer@example.test",
                subtotal=10,
                total=10,
            )
            old.get_model("orders", "OrderItem").objects.create(
                order=order,
                product=book,
                variant=variant,
                product_name=book.name,
                price=10,
                quantity=1,
            )
            order_ids.append(order.pk)

        MigrationExecutor(connection).migrate(latest)

        self.assertEqual(Product.objects.get(pk=book.pk).stock, 3)
        self.assertEqual(
            list(
                ProductVariant.objects.filter(product_id=book.pk).values_list(
                    "sku", "stock", "is_legacy_return"
                )
            ),
            [("OLD-STD", 0, False), ("OLD-WH", 3, False)],
        )
        client = APIClient()
        client.force_authenticate(get_user_model().objects.get(pk=buyer.pk))
        for order_id, variant_id in zip(order_ids, (None, default.pk), strict=True):
            response = client.post(f"/api/orders/{order_id}/cancel/")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(client.post(f"/api/orders/{order_id}/cancel/").status_code, 400)
            order = Order.objects.get(pk=order_id)
            self.assertEqual(order.status, Order.Status.CANCELLED)
            item = order.items.get()
            self.assertEqual(
                (item.product_id, item.variant_id, item.price, item.quantity),
                (book.pk, variant_id, Decimal("10.00"), 1),
            )
            self.assertEqual(order.history.get().to_status, Order.Status.CANCELLED)

        returned = ProductVariant.objects.get(product_id=book.pk, is_legacy_return=True)
        self.assertEqual((returned.stock, returned.is_active), (2, False))
        self.assertEqual(ProductVariant.objects.get(pk=warehouse.pk).stock, 3)
        self.assertEqual(Product.objects.get(pk=book.pk).stock, 3)
