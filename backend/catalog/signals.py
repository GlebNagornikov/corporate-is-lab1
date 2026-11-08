from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .caching import invalidate_catalog
from .models import BookEdition, Category, Product, ProductImage, ProductVariant, Review
from .restock import queue_restock


@receiver(pre_save, sender=Product)
def stock_before(sender, instance, **kwargs):
    instance._previous_stock = (
        Product.objects.filter(pk=instance.pk).values_list("stock", flat=True).first()
    )


@receiver(post_save, sender=Product)
def stock_after(sender, instance, **kwargs):
    if getattr(instance, "_previous_stock", None) == 0 and instance.stock > 0:
        queue_restock(instance.pk)


@receiver(post_save, sender=ProductVariant)
def variant_after(sender, instance, **kwargs):
    if not instance.is_default:
        from .inventory import refresh_inventory

        refresh_inventory(instance.product_id)


for model in (Product, BookEdition, Category, Review, ProductImage, ProductVariant):
    post_save.connect(lambda **kwargs: invalidate_catalog(), sender=model, weak=False)
    post_delete.connect(lambda **kwargs: invalidate_catalog(), sender=model, weak=False)
