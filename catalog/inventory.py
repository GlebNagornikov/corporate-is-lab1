from django.core.exceptions import ValidationError
from django.db.models import Min, Sum

from .models import Product, ProductVariant


def choose_variant(product, variant=None):
    if variant is not None:
        if variant.product_id != product.pk or not variant.is_active:
            raise ValidationError("Выберите активный вариант этого товара.")
        return variant
    if product.variants.filter(is_default=False, is_active=True).exists():
        raise ValidationError("Выберите вариант товара.")
    return ProductVariant.objects.get_or_create(
        product=product,
        is_default=True,
        defaults={
            "name": "Стандартный",
            "sku": f"default-{product.pk}",
            "price": product.price,
            "stock": product.stock,
        },
    )[0]


def refresh_inventory(product_id):
    variants = ProductVariant.objects.filter(
        product_id=product_id, is_default=False, is_active=True
    )
    if variants.exists():
        values = variants.aggregate(n=Sum("stock"), price=Min("price"))
        product = Product.objects.get(pk=product_id)
        product.stock = values["n"] or 0
        product.price = values["price"]
        if product.old_price is not None and product.old_price <= product.price:
            product.old_price = None
        product.save(update_fields=["stock", "price", "old_price"])
