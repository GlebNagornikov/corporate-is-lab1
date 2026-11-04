from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.inventory import choose_variant

from .models import Cart, CartItem

CART_SESSION_KEY = "cart_id"


def get_cart(request, create=False):
    """Корзина текущего посетителя. При create=False может вернуть None."""
    if request.user.is_authenticated:
        if create:
            return Cart.objects.get_or_create(user=request.user)[0]
        return Cart.objects.filter(user=request.user).first()
    cart_id = request.session.get(CART_SESSION_KEY)
    cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if cart is None and create:
        cart = Cart.objects.create()
        request.session[CART_SESSION_KEY] = cart.pk
    return cart


def set_quantity(cart, product, quantity, variant=None):
    """Ставит количество товара в корзине, но не больше остатка."""
    if not product.is_active:
        raise ValidationError("Товар снят с продажи.")
    variant = choose_variant(product, variant)
    stock = product.stock if variant.is_default else variant.stock
    quantity = min(quantity, stock)
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, product=product, variant=variant).delete()
        return 0
    CartItem.objects.update_or_create(
        cart=cart, product=product, variant=variant, defaults={"quantity": quantity}
    )
    cart.save(update_fields=["updated_at"])
    return quantity


def add_to_cart(cart, product, quantity=1, variant=None):
    variant = choose_variant(product, variant)
    current = (
        cart.items.filter(product=product, variant=variant)
        .values_list("quantity", flat=True)
        .first()
        or 0
    )
    return set_quantity(cart, product, current + quantity, variant=variant)


@transaction.atomic
def merge_carts(source, target):
    """Переносит товары гостя пользователю и удаляет гостевую корзину."""
    skipped = []
    for item in source.items.select_related("product", "variant"):
        if (
            not item.product.is_active
            or item.available_stock <= 0
            or (item.variant and not item.variant.is_active)
        ):
            skipped.append(item.product.name)
            continue
        add_to_cart(target, item.product, item.quantity, variant=item.variant)
    source.delete()
    return skipped
