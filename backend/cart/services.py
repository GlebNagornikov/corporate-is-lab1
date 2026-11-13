from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from catalog.inventory import choose_variant
from catalog.models import Product, ProductVariant

from .models import Cart, CartItem

CART_SESSION_KEY = "cart_id"
MAX_ORDER_AMOUNT = Decimal("9999999999.99")
CART_AMOUNT_ERROR = "Сумма товаров превышает допустимый предел заказа."


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


def _clear_empty_promo(cart):
    if cart.promo_code and not cart.items.exists():
        cart.promo_code = ""
        cart.save(update_fields=["promo_code", "updated_at"])


def _set_quantity(cart, product, quantity, variant, *, limit_to_order_amount=False):
    rows = _item_rows(cart, product, variant)
    stock = product.stock if variant.is_default else variant.stock
    quantity = min(quantity, stock)
    if quantity <= 0:
        rows.delete()
        _clear_empty_promo(cart)
        return 0
    previous_quantity = rows.aggregate(total=Sum("quantity"))["total"] or 0
    if quantity > previous_quantity:
        price = product.price if variant.is_default else variant.price
        other_total = sum(
            item.total
            for item in cart.items.exclude(pk__in=rows).select_related("product", "variant")
        )
        if other_total + price * quantity > MAX_ORDER_AMOUNT:
            if not limit_to_order_amount:
                raise ValidationError(CART_AMOUNT_ERROR)
            quantity = int((MAX_ORDER_AMOUNT - other_total) // price)
            if quantity <= previous_quantity:
                return previous_quantity
    CartItem.objects.update_or_create(
        cart=cart, product=product, variant=variant, defaults={"quantity": quantity}
    )
    if variant.is_default:
        rows.filter(variant__isnull=True).delete()
    cart.save(update_fields=["updated_at"])
    return quantity


def _add_quantity(cart, product, quantity, variant, *, limit_to_order_amount=False):
    current = _item_rows(cart, product, variant).aggregate(total=Sum("quantity"))["total"] or 0
    return _set_quantity(
        cart, product, current + quantity, variant, limit_to_order_amount=limit_to_order_amount
    )


@transaction.atomic
def set_quantity(cart, product, quantity, variant=None):
    """Ставит количество товара в корзине, но не больше остатка."""
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if quantity == 0:
        if variant is None:
            cart.items.filter(
                Q(variant__isnull=True) | Q(variant__is_default=True), product=product
            ).delete()
        else:
            _item_rows(cart, product, variant).delete()
        _clear_empty_promo(cart)
        return 0
    product = Product.objects.select_for_update().filter(pk=product.pk, is_active=True).first()
    if product is None:
        raise ValidationError("Товар снят с продажи.")
    if variant is not None:
        variant = product.variants.filter(pk=variant.pk, is_active=True).first()
        if variant is None:
            raise ValidationError("Этот вариант больше недоступен.")
    return _set_quantity(cart, product, quantity, choose_variant(product, variant))


@transaction.atomic
def add_to_cart(cart, product, quantity=1, variant=None):
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    product = Product.objects.select_for_update().filter(pk=product.pk, is_active=True).first()
    if product is None:
        raise ValidationError("Товар снят с продажи.")
    if variant is not None:
        variant = ProductVariant.objects.filter(
            pk=variant.pk, product=product, is_active=True
        ).first()
        if variant is None:
            raise ValidationError("Этот вариант больше недоступен.")
    variant = choose_variant(product, variant)
    if (product.stock if variant.is_default else variant.stock) <= 0:
        raise ValidationError("Книги больше нет в наличии.")
    _clear_empty_promo(cart)
    return _add_quantity(cart, product, quantity, variant)


@transaction.atomic
def remove_from_cart(cart, product_id, variant_id=None):
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    rows = cart.items.filter(product_id=product_id)
    if variant_id is not None:
        rows = rows.filter(variant_id=variant_id)
    rows.delete()
    _clear_empty_promo(cart)


@transaction.atomic
def merge_guest_items(user, lines, promo_code=""):
    """Переносит доступные позиции гостевой корзины из SPA."""
    cart, _ = Cart.objects.get_or_create(user=user)
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    _clear_empty_promo(cart)
    products = (
        Product.objects.active()
        .select_for_update()
        .order_by("pk")
        .in_bulk({line["product"] for line in lines})
    )
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
            _add_quantity(cart, product, line["quantity"], variant, limit_to_order_amount=True)
    if not cart.promo_code and promo_code and cart.items.exists():
        cart.promo_code = promo_code
        cart.save(update_fields=["promo_code", "updated_at"])
    return cart


@transaction.atomic
def set_cart_promo(cart, code):
    from orders.services import OrderError, get_valid_promo

    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if code:
        if not cart.items.exists():
            raise OrderError("Добавьте книгу в корзину, чтобы применить промокод.")
        get_valid_promo(code, subtotal=cart.total)
    cart.promo_code = code
    cart.save(update_fields=["promo_code", "updated_at"])
    return cart


@transaction.atomic
def merge_carts(source, target):
    """Переносит товары гостя пользователю и удаляет гостевую корзину."""
    skipped = []
    for item in source.items.select_related("product", "variant").order_by("product_id", "pk"):
        if (
            not item.product.is_active
            or item.available_stock <= 0
            or (item.variant and not item.variant.is_active)
        ):
            skipped.append(item.product.name)
            continue
        try:
            add_to_cart(target, item.product, item.quantity, variant=item.variant)
        except ValidationError:
            skipped.append(item.product.name)
    source.delete()
    return skipped
