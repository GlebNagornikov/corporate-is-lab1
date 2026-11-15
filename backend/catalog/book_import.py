from decimal import Decimal, InvalidOperation
from json import JSONDecodeError

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.utils import json

from .manager_serializers import ManagerBookWriteSerializer
from .models import BOOKS_ROOT_SLUG, Category, Product

MAX_BOOK_JSON_BYTES = 1024 * 1024
MAX_BOOK_JSON_ENTRIES = 1000


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValidationError("Поля в одном объекте JSON не должны повторяться.")
    return result


def read_entries(upload):
    try:
        contents = upload.read().decode("utf-8-sig")
    except UnicodeError as error:
        raise ValidationError("Сохраните JSON в кодировке UTF-8.") from error
    try:
        entries = json.loads(contents, object_pairs_hook=unique_object, parse_float=Decimal)
    except JSONDecodeError as error:
        raise ValidationError(
            f"Строка {error.lineno}, столбец {error.colno}: неверный JSON."
        ) from error
    except (ValueError, RecursionError, InvalidOperation) as error:
        raise ValidationError("Неверный формат JSON.") from error
    if not isinstance(entries, list) or not entries:
        raise ValidationError("Файл должен содержать непустой JSON-массив книг.")
    if len(entries) > MAX_BOOK_JSON_ENTRIES:
        raise ValidationError(f"В одном файле допускается до {MAX_BOOK_JSON_ENTRIES} книг.")

    allowed = set(ManagerBookWriteSerializer.Meta.fields) - {"image"}
    sku_field = serializers.CharField()
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValidationError(f"Запись {number}: ожидается объект книги.")
        unknown = entry.keys() - allowed
        if unknown:
            fields = ", ".join(repr(field) for field in sorted(unknown))
            raise ValidationError(f"Запись {number}: неизвестные поля — {fields}.")
        sku = entry.get("sku")
        if not isinstance(sku, str):
            raise ValidationError(f"Запись {number}, sku: укажите артикул строкой.")
        try:
            entry["sku"] = sku_field.run_validation(sku)
        except serializers.ValidationError as error:
            raise ValidationError(f"Запись {number}, sku: укажите допустимый артикул.") from error
    return entries


@transaction.atomic
def import_books(upload, *, dry_run):
    entries = read_entries(upload)
    skus = {entry["sku"] for entry in entries}
    products = Product.objects.filter(sku__in=skus).order_by("pk")
    if not dry_run:
        products = products.select_for_update()
    existing = {product.sku: product for product in products}
    genres = dict(Category.objects.exclude(slug=BOOKS_ROOT_SLUG).values_list("slug", "pk"))
    validated_entries, errors = [], []
    seen_skus, seen_slugs = set(), set()
    for number, entry in enumerate(entries, start=1):
        sku = entry["sku"]
        if sku in seen_skus:
            errors.append(f"Запись {number}: артикул {sku} уже встречался в файле.")
            continue
        seen_skus.add(sku)
        if "category" in entry:
            category = entry["category"]
            if not isinstance(category, str):
                errors.append(f"Запись {number}, category: укажите код жанра строкой.")
                continue
            category = category.strip()
            if category not in genres:
                errors.append(f"Запись {number}: жанр {category!r} не найден.")
                continue
            entry["category"] = genres[category]
        product = existing.get(sku)
        serializer = ManagerBookWriteSerializer(product, data=entry, partial=product is not None)
        if not serializer.is_valid():
            errors.extend(
                f"Запись {number}, {field}: {' '.join(messages)}"
                for field, messages in serializer.errors.items()
            )
            continue
        slug = serializer.validated_data.get("slug")
        if slug and slug in seen_slugs:
            errors.append(f"Запись {number}: адрес книги {slug} уже встречался в файле.")
            continue
        seen_slugs.add(slug)
        validated_entries.append((number, serializer))

    if errors:
        raise ValidationError(errors)
    if not dry_run:
        for number, serializer in validated_entries:
            try:
                serializer.save()
            except IntegrityError as error:
                raise ValidationError(
                    f"Запись {number}: конфликт данных. Проверьте артикул и адрес книги."
                ) from error
    return len(validated_entries)
