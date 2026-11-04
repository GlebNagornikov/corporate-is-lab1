import csv
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Category, Product, ProductVariant


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
