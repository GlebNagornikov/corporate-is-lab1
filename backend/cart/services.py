from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from catalog.inventory import choose_variant
from catalog.models import Product, ProductVariant

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


def _item_rows(cart, product, variant):
    variants = Q(variant=variant)
    if variant.is_default:
        variants |= Q(variant__isnull=True)
    return cart.items.filter(variants, product=product)


def _set_quantity(cart, product, quantity, variant):
    rows = _item_rows(cart, product, variant)
    stock = product.stock if variant.is_default else variant.stock
    quantity = min(quantity, stock)
    if quantity <= 0:
        rows.delete()
        return 0
    CartItem.objects.update_or_create(
        cart=cart, product=product, variant=variant, defaults={"quantity": quantity}
    )
    if variant.is_default:
        rows.filter(variant__isnull=True).delete()
    cart.save(update_fields=["updated_at"])
    return quantity


def _add_quantity(cart, product, quantity, variant):
    current = _item_rows(cart, product, variant).aggregate(total=Sum("quantity"))["total"] or 0
    return _set_quantity(cart, product, current + quantity, variant)


@transaction.atomic
def set_quantity(cart, product, quantity, variant=None):
    """Ставит количество товара в корзине, но не больше остатка."""
    if not product.is_active:
        raise ValidationError("Товар снят с продажи.")
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    return _set_quantity(cart, product, quantity, choose_variant(product, variant))


@transaction.atomic
def add_to_cart(cart, product, quantity=1, variant=None):
    if not product.is_active:
        raise ValidationError("Товар снят с продажи.")
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    return _add_quantity(cart, product, quantity, choose_variant(product, variant))


@transaction.atomic
def remove_from_cart(cart, product_id, variant_id=None):
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    rows = cart.items.filter(product_id=product_id)
    if variant_id is not None:
        rows = rows.filter(variant_id=variant_id)
    rows.delete()


@transaction.atomic
def merge_guest_items(user, lines):
    """Переносит доступные позиции гостевой корзины из SPA."""
    cart, _ = Cart.objects.get_or_create(user=user)
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    products = Product.objects.active().in_bulk({line["product"] for line in lines})
    variants = ProductVariant.objects.filter(is_active=True).in_bulk(
        {line["variant"] for line in lines if "variant" in line}
    )
    for line in lines:
        product = products.get(line["product"])
        variant_id = line.get("variant")
        variant = variants.get(variant_id)
        if product is None or (variant_id is not None and variant is None):
            continue
        try:
            variant = choose_variant(product, variant)
        except ValidationError:
            continue
        stock = product.stock if variant.is_default else variant.stock
        if variant.is_active and stock > 0:
            _add_quantity(cart, product, line["quantity"], variant)
    return cart


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
