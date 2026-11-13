from django.db.models.query import QuerySet
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .caching import invalidate_catalog
from .models import BookEdition, Category, Product, ProductImage, ProductVariant, Review
from .services import record_restock


@receiver(pre_save, sender=Product)
def stock_before(sender, instance, update_fields, **kwargs):
    instance._was_available = None
    if not instance.pk or (
        update_fields is not None and not {"stock", "is_active"} & update_fields
    ):
        return
    previous = (
        Product.objects.select_for_update()
        .filter(pk=instance.pk)
        .values_list("stock", "is_active")
        .first()
    )
    if previous is not None:
        stock, active = previous
        instance._was_available = stock > 0 and active
        if update_fields is None or "stock" in update_fields:
            stock = instance.stock
        if update_fields is None or "is_active" in update_fields:
            active = instance.is_active
        instance._is_available = stock > 0 and active


@receiver(post_save, sender=Product)
def stock_after(sender, instance, **kwargs):
    if getattr(instance, "_was_available", None) is False and instance._is_available:
        record_restock(instance.pk)


@receiver(post_save, sender=ProductVariant)
def variant_after(sender, instance, **kwargs):
    if not instance.is_default:
        from .inventory import refresh_inventory

        refresh_inventory(
            instance.product_id,
            variant_deleted=getattr(instance, "_legacy_variant_deactivated", False),
        )


def _deleting_product(origin):
    return isinstance(origin, Product) or (isinstance(origin, QuerySet) and origin.model is Product)


@receiver(pre_delete, sender=ProductVariant)
def lock_product_before_variant_delete(sender, instance, origin, **kwargs):
    if not instance.is_default and not _deleting_product(origin):
        Product.objects.select_for_update().get(pk=instance.product_id)


@receiver(post_delete, sender=ProductVariant)
def refresh_after_variant_delete(sender, instance, origin, **kwargs):
    if not instance.is_default and not _deleting_product(origin):
        from .inventory import refresh_inventory

        refresh_inventory(
            instance.product_id, variant_deleted=not instance.is_legacy_return or instance.is_active
        )


for model in (Product, BookEdition, Category, Review, ProductImage, ProductVariant):
    post_save.connect(lambda **kwargs: invalidate_catalog(), sender=model, weak=False)
    post_delete.connect(lambda **kwargs: invalidate_catalog(), sender=model, weak=False)
