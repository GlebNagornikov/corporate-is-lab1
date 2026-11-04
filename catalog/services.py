import csv
import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Min, Sum

from .models import Category, Product, ProductVariant, StockSubscription, WishlistItem

KEY = "comparison"


def choose_variant(product, variant=None):
    if variant is not None:
        if variant.product_id != product.pk or not variant.is_active:
            raise ValidationError("Выберите активный вариант этого товара.")
        if variant.is_default and product.variants.filter(is_default=False).exists():
            raise ValidationError("Выберите размер и цвет товара.")
        return variant
    if product.variants.filter(is_default=False).exists():
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
    if ProductVariant.objects.filter(product_id=product_id, is_default=False).exists():
        values = variants.aggregate(n=Sum("stock"), price=Min("price"))
        product = Product.objects.get(pk=product_id)
        product.stock = values["n"] or 0
        product.price = values["price"] or product.price
        if product.old_price is not None and product.old_price <= product.price:
            product.old_price = None
        product.save(update_fields=["stock", "price", "old_price"])


def set_favorite(user, product, enabled=True):
    if enabled:
        return WishlistItem.objects.get_or_create(user=user, product=product)[0]
    WishlistItem.objects.filter(user=user, product=product).delete()


def root_category(category_id):
    parents = dict(Category.objects.values_list("pk", "parent_id"))
    seen = set()
    while parents.get(category_id):
        if category_id in seen:
            raise ValidationError("Цикл категорий.")
        seen.add(category_id)
        category_id = parents[category_id]
    return category_id


def comparison_products(session):
    return list(
        Product.objects.active().with_rating().filter(pk__in=session.get(KEY, [])).order_by("pk")
    )


def add_comparison(session, product):
    products = comparison_products(session)
    if product.pk in [p.pk for p in products]:
        return
    if len(products) >= 4:
        raise ValidationError("Можно сравнить не больше четырёх товаров.")
    if products and root_category(products[0].category_id) != root_category(product.category_id):
        raise ValidationError("Выберите товары одной категории верхнего уровня.")
    session[KEY] = [p.pk for p in products] + [product.pk]


def comparison_rows(products):
    rows = []
    for label, field in [
        ("Цена от, ₽", "price"),
        ("Скидка, %", "discount_percent"),
        ("Рейтинг", "rating"),
        ("В наличии", "in_stock"),
    ]:
        values = [
            str(getattr(p, field) if getattr(p, field) is not None else "—") for p in products
        ]
        rows.append((label, values, len(set(values)) > 1))
    keys = sorted({key for p in products for key in p.attributes})
    for key in keys:
        values = [str(p.attributes.get(key, "—")) for p in products]
        rows.append((key, values, len(set(values)) > 1))
    return rows


@transaction.atomic
def subscribe(product, email):
    product = Product.objects.select_for_update().get(pk=product.pk)
    if product.stock > 0 or not product.is_active:
        raise ValidationError("Подписка доступна только для отсутствующего товара.")
    email = email.strip().lower()
    validate_email(email)
    subscription, _ = StockSubscription.objects.update_or_create(
        product=product, email=email, defaults={"completed": False}
    )
    return subscription


def deliver_restock(product_id):
    for pk in StockSubscription.objects.filter(product_id=product_id, completed=False).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            subscription = (
                StockSubscription.objects.select_for_update().select_related("product").get(pk=pk)
            )
            if subscription.completed:
                continue
            product = subscription.product
            send_mail(
                f"В наличии: {product.name}",
                f"Товар снова в продаже: {settings.SITE_URL}{product.get_absolute_url()}",
                None,
                [subscription.email],
            )
            subscription.completed = True
            subscription.save(update_fields=["completed"])


def queue_restock(product_id):
    from config.request_logging import request_id

    from .tasks import send_restock

    identifier = request_id()
    transaction.on_commit(
        lambda: send_restock.apply_async(args=[product_id], headers={"request_id": identifier})
    )


@transaction.atomic
def import_products(stream, *, dry_run=False):
    reader = csv.DictReader(stream)
    required = {"sku", "name", "slug", "category", "price", "stock"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValidationError("Обязательные столбцы: " + ", ".join(sorted(required)))
    rows, errors, seen = [], [], set()
    slugs, variant_skus = set(), set()
    for number, row in enumerate(reader, 2):
        try:
            sku = (row.get("sku") or "").strip()
            if not sku or sku in seen:
                raise ValidationError("Пустой или повторный артикул.")
            seen.add(sku)
            category = Category.objects.get(slug=row["category"])
            product = Product.objects.filter(sku=sku).first() or Product(sku=sku)
            for key in ("name", "slug"):
                setattr(product, key, row[key].strip())
            product.category = category
            product.price, product.stock = Decimal(row["price"]), int(row["stock"])
            if not product.price.is_finite() or product.price <= 0 or product.stock < 0:
                raise ValidationError("Цена должна быть положительной, остаток неотрицательным.")
            if row.get("attributes"):
                product.attributes = json.loads(row["attributes"])
                if not isinstance(product.attributes, dict):
                    raise ValidationError("Характеристики должны быть JSON-объектом.")
            if product.slug in slugs:
                raise ValidationError("Повторный slug в файле.")
            slugs.add(product.slug)
            product.full_clean()
            variant = None
            if row.get("variant_sku"):
                if row["variant_sku"] in variant_skus:
                    raise ValidationError("Повторный артикул варианта в файле.")
                variant_skus.add(row["variant_sku"])
                variant = ProductVariant.objects.filter(sku=row["variant_sku"]).first()
                if variant and variant.product_id != product.pk:
                    raise ValidationError("Артикул варианта принадлежит другому товару.")
                variant = variant or ProductVariant(sku=row["variant_sku"])
                variant.name = row.get("variant_name") or "Вариант"
                variant.price = Decimal(row.get("variant_price") or row["price"])
                variant.stock = int(row.get("variant_stock") or row["stock"])
                variant.full_clean(exclude=["product"])
            rows.append((product, variant))
        except (
            ValidationError,
            Category.DoesNotExist,
            ValueError,
            TypeError,
            InvalidOperation,
        ) as error:
            message = (
                "; ".join(error.messages)
                if isinstance(error, ValidationError)
                else "Неверные данные или категория: " + str(error)
            )
            errors.append(f"Строка {number}: {message}")
    if errors:
        raise ValidationError(errors)
    try:
        with transaction.atomic():
            return _save_rows(rows, dry_run)
    except IntegrityError as error:
        raise ValidationError("Конфликт уникальности: файл не применён.") from error


def _save_rows(rows, dry_run):
    for product, variant in rows:
        product.save()
        if variant:
            variant.product = product
            variant.save()
    if dry_run:
        transaction.set_rollback(True)
    return len(rows)
