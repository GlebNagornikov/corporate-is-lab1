from django.core.exceptions import ValidationError
from django.db.models import Sum

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
        Product.objects.filter(pk=product_id).update(
            stock=variants.aggregate(n=Sum("stock"))["n"] or 0
        )
