import csv
import json
from decimal import Decimal, InvalidOperation
from hashlib import blake2s

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Min, Sum
from django.utils import timezone

from .models import (
    BOOKS_ROOT_SLUG,
    VISIBLE_VARIANTS,
    Category,
    Product,
    ProductVariant,
    RestockNotification,
    StockSubscription,
    WishlistItem,
)

KEY = "comparison"


@transaction.atomic
def create_genre(name):
    root, _ = Category.objects.select_for_update().get_or_create(
        slug=BOOKS_ROOT_SLUG, defaults={"name": "Книги"}
    )
    if Category.objects.filter(name__iexact=name).exists():
        raise ValidationError({"name": "Жанр с таким названием уже есть."})
    slug = "genre-" + blake2s(name.casefold().encode(), digest_size=12).hexdigest()
    try:
        return Category.objects.create(name=name, slug=slug, parent=root)
    except IntegrityError as error:
        raise ValidationError({"name": "Жанр с таким названием уже есть."}) from error


def choose_variant(product, variant=None):
    if variant is not None:
        if variant.product_id != product.pk or not variant.is_active:
            raise ValidationError("Выберите активный вариант этого товара.")
        if (
            variant.is_default
            and product.variants.filter(VISIBLE_VARIANTS, is_default=False).exists()
        ):
            raise ValidationError("Выберите размер и цвет товара.")
        return variant
    if product.variants.filter(VISIBLE_VARIANTS, is_default=False).exists():
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


@transaction.atomic
def refresh_inventory(product_id, *, variant_deleted=False):
    product = Product.objects.select_for_update().get(pk=product_id)
    variants = ProductVariant.objects.filter(
        product_id=product_id, is_default=False, is_active=True
    )
    if (
        variant_deleted
        or ProductVariant.objects.filter(
            VISIBLE_VARIANTS, product_id=product_id, is_default=False
        ).exists()
    ):
        values = variants.aggregate(n=Sum("stock"), price=Min("price"))
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


@transaction.atomic
def subscribe_personally(product_id, user):
    product = Product.objects.select_for_update().filter(pk=product_id, is_active=True).first()
    if product is None:
        raise Product.DoesNotExist
    if product.in_stock:
        raise ValidationError("Подписка доступна только для отсутствующего товара.")
    RestockNotification.objects.get_or_create(user=user, product=product, notified_at=None)


def record_restock(product_id):
    RestockNotification.objects.filter(product_id=product_id, notified_at=None).update(
        notified_at=timezone.now()
    )
    queue_restock(product_id)


def deliver_restock(product_id):
    for pk in StockSubscription.objects.filter(product_id=product_id, completed=False).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            product = (
                Product.objects.select_for_update()
                .filter(pk=product_id, is_active=True, stock__gt=0)
                .first()
            )
            if product is None:
                return
            subscription = (
                StockSubscription.objects.select_for_update().filter(pk=pk, completed=False).first()
            )
            if subscription is None:
                continue
            send_mail(
                f"В наличии: {product.name}",
                f"Товар снова в продаже: {settings.SITE_URL.rstrip('/')}/products/{product.slug}",
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
        lambda: send_restock.apply_async(args=[product_id], headers={"request_id": identifier}),
        robust=True,
    )


@transaction.atomic
def import_products(stream, *, dry_run=False):
    reader = csv.DictReader(stream)
    required = {"sku", "name", "slug", "category", "price", "stock"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValidationError("Обязательные столбцы: " + ", ".join(sorted(required)))
    entries = list(reader)
    products = {
        product.sku: product
        for product in Product.objects.select_for_update()
        .filter(sku__in={(row.get("sku") or "").strip() for row in entries})
        .order_by("pk")
    }
    rows, errors, seen = [], [], set()
    slugs, variant_skus = set(), set()
    for number, row in enumerate(entries, 2):
        try:
            sku = (row.get("sku") or "").strip()
            if not sku or sku in seen:
                raise ValidationError("Пустой или повторный артикул.")
            seen.add(sku)
            category = Category.objects.get(slug=row["category"])
            product = products.get(sku) or Product(sku=sku)
            has_variants = (
                product.pk and product.variants.filter(VISIBLE_VARIANTS, is_default=False).exists()
            )
            for key in ("name", "slug"):
                setattr(product, key, (row[key] or "").strip())
            product.category = category
            price, stock = Decimal(row["price"]), int(row["stock"])
            if not price.is_finite() or price <= 0 or stock < 0:
                raise ValidationError("Цена должна быть положительной, остаток неотрицательным.")
            if not has_variants and not (product.pk and row.get("variant_sku")):
                product.price, product.stock = price, stock
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
                if variant.is_default:
                    raise ValidationError("Стандартный вариант обновляется полями товара.")
                variant.name = row.get("variant_name") or "Вариант"
                variant.price = Decimal(row.get("variant_price") or row["price"])
                variant.stock = int(row.get("variant_stock") or row["stock"])
                variant.full_clean(exclude=["product"])
                if variant.is_active and product.pk:
                    other_stock = (
                        product.variants.filter(is_active=True, is_default=False)
                        .exclude(pk=variant.pk)
                        .aggregate(total=Sum("stock", default=0))["total"]
                    )
                    if other_stock + variant.stock > 2147483647:
                        raise ValidationError("Слишком большой суммарный остаток.")
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
