import hashlib
import hmac
import logging
from collections import Counter
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Max, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404

from catalog.caching import invalidate_catalog
from catalog.inventory import refresh_inventory
from catalog.models import VISIBLE_VARIANTS, Product, ProductVariant

from .events import publish_order_change
from .models import Order, OrderItem, OrderStatusLog, Payment, PromoCode
from .tasks import queue_order_email

logger = logging.getLogger(__name__)
COURIER_COST = Decimal("500")
FREE_DELIVERY_FROM = Decimal("5000")
MAX_COPIES_PER_EDITION = 5


class OrderError(Exception):
    """Операцию с заказом нельзя выполнить. Текст можно показать пользователю."""


def get_valid_promo(code, *, subtotal=None, lock=False):
    queryset = PromoCode.objects.select_for_update() if lock else PromoCode.objects
    promo = queryset.filter(code=code.strip().upper()).first()
    if promo is None:
        raise OrderError("Промокод не найден.")
    reason = promo.rejection_reason(subtotal)
    if reason:
        raise OrderError(reason)
    return promo


def promo_discount(promo, subtotal):
    return (subtotal * promo.discount_percent / 100).quantize(Decimal("0.01"))


def delivery_cost_for(method, amount):
    if method == Order.Delivery.COURIER and amount < FREE_DELIVERY_FROM:
        return COURIER_COST
    return Decimal("0")


@transaction.atomic
def place_order(
    *,
    user,
    cart,
    delivery_method,
    full_name,
    phone,
    email,
    address="",
    comment="",
    promo_code=None,
    address_book=None,
):
    """Оформляет заказ: списывает остатки, применяет промокод, очищает корзину."""
    from cart.models import Cart
    from cart.services import CART_AMOUNT_ERROR, MAX_ORDER_AMOUNT

    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if cart.user_id != user.pk:
        raise OrderError("Это не ваша корзина.")
    items = list(cart.items.select_related("product", "variant"))
    if not items:
        raise OrderError("Корзина пуста.")
    if address_book is not None:
        from accounts.models import Address

        selected = Address.objects.filter(pk=address_book.pk, user=user).first()
        if selected is None:
            raise OrderError("Это не ваш адрес.")
        address = selected.snapshot
    if delivery_method == Order.Delivery.COURIER and not address.strip():
        raise OrderError("Для доставки курьером укажите адрес.")
    # Блокируем товары в одинаковом порядке, чтобы избежать взаимоблокировок.
    products = {
        p.pk: p
        for p in Product.objects.select_for_update()
        .filter(pk__in=[item.product_id for item in items])
        .order_by("pk")
    }
    quantities = Counter()
    for item in items:
        if item.product_id not in products:
            raise OrderError(f"Товар «{item.product.name}» больше недоступен.")
        quantities[item.product_id] += item.quantity
    for product_id, quantity in quantities.items():
        if quantity > MAX_COPIES_PER_EDITION:
            raise OrderError(
                f"«{products[product_id].name}»: в одном заказе можно купить не больше "
                f"{MAX_COPIES_PER_EDITION} экземпляров издания с учётом всех вариантов. "
                f"В корзине {quantity}."
            )
    variants = {
        v.pk: v
        for v in ProductVariant.objects.select_for_update()
        .filter(pk__in=[i.variant_id for i in items if i.variant_id])
        .order_by("pk")
    }
    products_with_variants = set(
        ProductVariant.objects.filter(
            VISIBLE_VARIANTS, product_id__in=products, is_default=False
        ).values_list("product_id", flat=True)
    )
    reserved = Counter()
    for item in items:
        product = products[item.product_id]
        variant = variants.get(item.variant_id)
        item.product = product
        if item.variant_id and variant is None:
            raise OrderError("Вариант товара недоступен.")
        if product.pk in products_with_variants and (variant is None or variant.is_default):
            raise OrderError(f"«{product.name}»: удалите старую позицию и выберите вариант книги.")
        if variant:
            item.variant = variant
        if variant and (variant.product_id != product.pk or not variant.is_active):
            raise OrderError("Вариант товара недоступен.")
        if not product.is_active:
            raise OrderError(f"Товар «{product.name}» снят с продажи.")
        # Старая строка без варианта и вариант по умолчанию используют один остаток.
        stock_key = (product.pk, variant.pk if variant and not variant.is_default else None)
        reserved[stock_key] += item.quantity
        stock = item.available_stock
        if stock < reserved[stock_key]:
            raise OrderError(f"Товара «{product.name}» осталось только {stock} шт.")
    subtotal = sum(item.unit_price * item.quantity for item in items)
    if subtotal > MAX_ORDER_AMOUNT:
        raise OrderError(CART_AMOUNT_ERROR)
    code = cart.promo_code if promo_code is None else promo_code
    promo = get_valid_promo(code, subtotal=subtotal, lock=True) if code.strip() else None
    discount = promo_discount(promo, subtotal) if promo else Decimal("0")
    delivery_cost = delivery_cost_for(delivery_method, subtotal - discount)
    total = subtotal - discount + delivery_cost
    if total > MAX_ORDER_AMOUNT:
        raise OrderError(CART_AMOUNT_ERROR)
    order = Order.objects.create(
        user=user,
        full_name=full_name,
        phone=phone,
        email=email,
        delivery_method=delivery_method,
        address=address,
        comment=comment,
        promo_code=promo,
        subtotal=subtotal,
        discount=discount,
        delivery_cost=delivery_cost,
        total=total,
    )
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            product=products[item.product_id],
            product_name=products[item.product_id].name,
            variant=item.variant,
            variant_name=item.variant.name if item.variant else "",
            price=item.unit_price,
            quantity=item.quantity,
        )
        for item in items
    )
    for (product_id, variant_id), quantity in reserved.items():
        if variant_id is None:
            product = products[product_id]
            stock = product.stock - quantity
            Product.objects.filter(pk=product_id).update(stock=stock)
            ProductVariant.objects.filter(product_id=product_id, is_default=True).update(
                stock=stock, price=product.price
            )
        else:
            ProductVariant.objects.filter(pk=variant_id).update(stock=F("stock") - quantity)
    for product_id in products_with_variants:
        refresh_inventory(product_id)
    if promo:
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
    OrderStatusLog.objects.create(
        order=order, to_status=order.status, changed_by=user, comment="Заказ оформлен"
    )
    cart.items.all().delete()
    cart.promo_code = ""
    cart.save(update_fields=["promo_code", "updated_at"])
    invalidate_catalog()
    queue_order_email(order, "placed")
    logger.info(
        "Оформлен заказ №%s на сумму %s, покупатель %s",
        order.pk,
        order.total,
        user,
        extra={"order_id": order.pk},
    )
    return order


@transaction.atomic
def change_status(order, new_status, *, by, comment="", payment_verified=False):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if new_status == Order.Status.PAID and not payment_verified:
        raise OrderError("Оплата подтверждается только платёжным шлюзом.")
    if not order.can_change_to(new_status):
        raise OrderError(
            f"Заказ №{order.pk}: нельзя перейти из «{order.get_status_display()}» "
            f"в «{Order.Status(new_status).label}»."
        )
    if new_status == Order.Status.CANCELLED:
        items = list(order.items.all())
        products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(pk__in=[item.product_id for item in items])
            .order_by("pk")
        }
        products_with_variants = set(
            ProductVariant.objects.filter(
                VISIBLE_VARIANTS, product_id__in=products, is_default=False
            ).values_list("product_id", flat=True)
        )
        for item in items:
            if item.product_id in products_with_variants and (
                not item.variant or item.variant.is_default
            ):
                product = products[item.product_id]
                # Старый заказ не определяет, к какому из новых вариантов относится экземпляр.
                variant, _ = product.variants.get_or_create(
                    is_legacy_return=True,
                    defaults={
                        "name": "Стандартный (до введения вариантов)",
                        "sku": f"legacy-return-{uuid4().hex}",
                        "price": product.price,
                        "is_active": False,
                    },
                )
                ProductVariant.objects.filter(pk=variant.pk).update(
                    stock=F("stock") + item.quantity
                )
                refresh_inventory(item.product_id)
                continue
            if not item.variant or item.variant.is_default:
                product = products[item.product_id]
                product.stock += item.quantity
                product.save(update_fields=["stock"])
                ProductVariant.objects.filter(product=product, is_default=True).update(
                    stock=product.stock, price=product.price
                )
            else:
                ProductVariant.objects.filter(pk=item.variant_id).update(
                    stock=F("stock") + item.quantity
                )
                refresh_inventory(item.product_id)
    old_status = order.status
    if new_status == Order.Status.CANCELLED:
        invalidate_catalog()
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusLog.objects.create(
        order=order, from_status=old_status, to_status=new_status, changed_by=by, comment=comment
    )
    transaction.on_commit(lambda: publish_order_change(order.pk), robust=True)
    queue_order_email(order, "status")
    logger.info(
        "Заказ №%s: %s → %s (%s)",
        order.pk,
        old_status,
        new_status,
        by,
        extra={"order_id": order.pk},
    )
    return order


@transaction.atomic
def cancel_by_customer(order, user):
    # Решение принимается по свежей заблокированной строке, а не устаревшему объекту.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.user_id != user.pk:
        raise OrderError("Это не ваш заказ.")
    if not order.can_be_cancelled_by_customer:
        raise OrderError("Заказ уже в работе, отменить его можно только через менеджера.")
    return change_status(order, Order.Status.CANCELLED, by=user, comment="Отменён покупателем")


def signature(body):
    return hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


@transaction.atomic
def begin_payment(order, user):
    order = get_object_or_404(Order.objects.select_for_update(), pk=order.pk, user=user)
    if not order.can_be_paid:
        raise ValidationError("Оплатить можно только новый заказ.")
    return Payment.objects.create(order=order, amount=order.total)


@transaction.atomic
def apply_payment(payment_id, outcome):
    # The order is always locked before the payment, matching other order workflows.
    payment = get_object_or_404(Payment, pk=payment_id)
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != "pending":
        return payment
    if outcome == "success":
        if order.status != Order.Status.NEW or payment.amount != order.total:
            raise ValidationError("Заказ уже обработан или сумма изменилась.")
        change_status(
            order,
            Order.Status.PAID,
            by=order.user,
            comment="Подтверждено платёжным шлюзом",
            payment_verified=True,
        )
    payment.status = outcome
    payment.save(update_fields=["status"])
    return payment


@transaction.atomic
def simulate_payment(order, user, outcome):
    payment = begin_payment(order, user)
    apply_payment(payment.pk, outcome)
    order.refresh_from_db()
    return order


def sales_report(start=None, end=None, *, books_only=False):
    orders = Order.objects.all()
    if start:
        orders = orders.filter(created_at__date__gte=start)
    if end:
        orders = orders.filter(created_at__date__lte=end)
    active = orders.exclude(status=Order.Status.CANCELLED)
    order_items = OrderItem.objects.filter(order__in=active)
    if books_only:
        order_items = order_items.filter(product__book__isnull=False)
    items = order_items.values("product_id").annotate(
        name=Max("product_name"),
        revenue=Sum(
            F("price") * F("quantity"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        ),
        quantity=Sum("quantity"),
    )
    summary = active.aggregate(
        count=Count("pk"), revenue=Sum("total", default=0), average=Avg("total", default=0)
    )
    summary["average"] = summary["average"].quantize(Decimal("0.01"))
    return {
        "summary": summary,
        "statuses": list(
            orders.order_by().values("status").annotate(count=Count("pk")).order_by("status")
        ),
        "deliveries": list(
            active.order_by()
            .values("delivery_method")
            .annotate(count=Count("pk"), revenue=Sum("total"))
            .order_by("delivery_method")
        ),
        "daily": list(
            active.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("pk"), revenue=Sum("total"))
            .order_by("day")
        ),
        "top_quantity": list(items.order_by("-quantity", "product_id")[:10]),
        "top_revenue": list(items.order_by("-revenue", "product_id")[:10]),
    }
