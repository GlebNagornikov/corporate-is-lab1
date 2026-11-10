import csv
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .manager_serializers import ManagerBookWriteSerializer
from .models import BOOKS_ROOT_SLUG, Category, Product

MAX_BOOK_CSV_BYTES = 1024 * 1024
MAX_BOOK_CSV_ROWS = 1000


def read_rows(upload):
    try:
        contents = upload.read().decode("utf-8-sig")
    except UnicodeError as error:
        raise ValidationError("Сохраните CSV в кодировке UTF-8.") from error
    header = contents.splitlines()[0] if contents else ""
    delimiter = ";" if ";" in header and "," not in header else ","
    reader = csv.DictReader(StringIO(contents), delimiter=delimiter, strict=True)
    try:
        fields = reader.fieldnames or []
        if "sku" not in fields:
            raise ValidationError("В заголовке CSV обязателен столбец sku.")
        if len(fields) != len(set(fields)):
            raise ValidationError("В заголовке CSV повторяются названия столбцов.")
        allowed = set(ManagerBookWriteSerializer.Meta.fields) - {"image"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValidationError("Неизвестные столбцы: " + ", ".join(sorted(unknown)))
        rows = []
        for row in reader:
            number = reader.line_num
            if len(rows) == MAX_BOOK_CSV_ROWS:
                raise ValidationError(f"В одном файле допускается до {MAX_BOOK_CSV_ROWS} книг.")
            if None in row or None in row.values():
                raise ValidationError(f"Строка {number}: число значений не совпадает с заголовком.")
            rows.append((number, row))
    except csv.Error as error:
        raise ValidationError(f"Строка {reader.line_num}: неверный формат CSV.") from error
    if not rows:
        raise ValidationError("Добавьте в CSV хотя бы одну строку с книгой.")
    return rows


@transaction.atomic
def import_books(upload, *, dry_run):
    rows = read_rows(upload)
    skus = {row["sku"].strip() for _, row in rows}
    products = Product.objects.filter(sku__in=skus).order_by("pk")
    if not dry_run:
        products = products.select_for_update()
    existing = {product.sku: product for product in products}
    genres = dict(Category.objects.exclude(slug=BOOKS_ROOT_SLUG).values_list("slug", "pk"))
    validated_rows, errors = [], []
    seen_skus, seen_slugs = set(), set()
    for number, row in rows:
        sku = row["sku"].strip()
        if sku in seen_skus:
            errors.append(f"Строка {number}: артикул {sku} уже встречался в файле.")
            continue
        seen_skus.add(sku)
        if "category" in row:
            category = row["category"].strip()
            if category not in genres:
                errors.append(f"Строка {number}: жанр «{category}» не найден.")
                continue
            row["category"] = genres[category]
        if row.get("old_price") == "":
            row["old_price"] = None
        product = existing.get(sku)
        serializer = ManagerBookWriteSerializer(product, data=row, partial=product is not None)
        if not serializer.is_valid():
            errors.extend(
                f"Строка {number}, {field}: {' '.join(messages)}"
                for field, messages in serializer.errors.items()
            )
            continue
        slug = serializer.validated_data.get("slug")
        if slug and slug in seen_slugs:
            errors.append(f"Строка {number}: адрес книги {slug} уже встречался в файле.")
            continue
        seen_slugs.add(slug)
        validated_rows.append((number, serializer))

    if errors:
        raise ValidationError(errors)
    if not dry_run:
        for number, serializer in validated_rows:
            try:
                serializer.save()
            except IntegrityError as error:
                raise ValidationError(
                    f"Строка {number}: конфликт данных. Проверьте артикул и адрес книги."
                ) from error
    return len(validated_rows)
