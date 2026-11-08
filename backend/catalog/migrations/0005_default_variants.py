from django.db import migrations


def populate(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Variant = apps.get_model("catalog", "ProductVariant")
    CartItem = apps.get_model("cart", "CartItem")
    OrderItem = apps.get_model("orders", "OrderItem")
    for product in Product.objects.all().iterator():
        variant, _ = Variant.objects.get_or_create(
            product_id=product.pk, is_default=True,
            defaults={"name": "Стандартный", "sku": f"default-{product.pk}",
                      "price": product.price, "stock": product.stock},
        )
        CartItem.objects.filter(product_id=product.pk, variant__isnull=True).update(variant_id=variant.pk)
        OrderItem.objects.filter(product_id=product.pk, variant__isnull=True).update(variant_id=variant.pk, variant_name="Стандартный")


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_productvariant"),
        ("cart", "0002_remove_cartitem_one_line_per_product_and_more"),
        ("orders", "0002_orderitem_variant_orderitem_variant_name"),
    ]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
