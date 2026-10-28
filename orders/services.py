import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from catalog.models import Product

from .models import Order, OrderItem, OrderStatusLog, PromoCode
from .notifications import send_order_placed, send_status_changed

logger = logging.getLogger(__name__)
COURIER_COST = Decimal("500")
FREE_DELIVERY_FROM = Decimal("5000")


class OrderError(Exception):
    """Операцию с заказом нельзя выполнить. Текст можно показать пользователю."""


def get_valid_promo(code, *, lock=False):
    queryset = PromoCode.objects.select_for_update() if lock else PromoCode.objects
    promo = queryset.filter(code=code.strip().upper()).first()
    if promo is None or not promo.is_valid_now():
        raise OrderError("Промокод не найден или больше не действует.")
    return promo


def delivery_cost_for(method, amount):
    if method == Order.Delivery.COURIER and amount < FREE_DELIVERY_FROM:
        return COURIER_COST
    return Decimal("0")


@transaction.atomic
def place_order(
    *, user, cart, delivery_method, full_name, phone, email, address="", comment="", promo_code=""
):
    """Оформляет заказ: списывает остатки, применяет промокод, очищает корзину."""
    items = list(cart.items.all())
    if not items:
        raise OrderError("Корзина пуста.")
    if delivery_method == Order.Delivery.COURIER and not address.strip():
        raise OrderError("Для доставки курьером укажите адрес.")
    # Блокируем товары в одинаковом порядке, чтобы избежать взаимоблокировок.
    products = {
        p.pk: p
        for p in Product.objects.select_for_update()
        .filter(pk__in=[item.product_id for item in items])
        .order_by("pk")
    }
    for item in items:
        product = products[item.product_id]
        if not product.is_active:
            raise OrderError(f"Товар «{product.name}» снят с продажи.")
        if product.stock < item.quantity:
            raise OrderError(f"Товара «{product.name}» осталось только {product.stock} шт.")
    promo = get_valid_promo(promo_code, lock=True) if promo_code.strip() else None
    subtotal = sum(products[item.product_id].price * item.quantity for item in items)
    discount = Decimal("0")
    if promo:
        discount = (subtotal * promo.discount_percent / 100).quantize(Decimal("0.01"))
    delivery_cost = delivery_cost_for(delivery_method, subtotal - discount)
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
        total=subtotal - discount + delivery_cost,
    )
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            product=products[item.product_id],
            product_name=products[item.product_id].name,
            price=products[item.product_id].price,
            quantity=item.quantity,
        )
        for item in items
    )
    for item in items:
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") - item.quantity)
    if promo:
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
    OrderStatusLog.objects.create(
        order=order, to_status=order.status, changed_by=user, comment="Заказ оформлен"
    )
    cart.items.all().delete()
    transaction.on_commit(lambda: send_order_placed(order.pk))
    logger.info("Оформлен заказ №%s на сумму %s, покупатель %s", order.pk, order.total, user)
    return order


@transaction.atomic
def change_status(order, new_status, *, by, comment=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_change_to(new_status):
        raise OrderError(
            f"Заказ №{order.pk}: нельзя перейти из «{order.get_status_display()}» "
            f"в «{Order.Status(new_status).label}»."
        )
    if new_status == Order.Status.CANCELLED:
        for item in order.items.all():
            Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    old_status = order.status
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusLog.objects.create(
        order=order, from_status=old_status, to_status=new_status, changed_by=by, comment=comment
    )
    transaction.on_commit(lambda: send_status_changed(order.pk))
    logger.info("Заказ №%s: %s → %s (%s)", order.pk, old_status, new_status, by)
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
