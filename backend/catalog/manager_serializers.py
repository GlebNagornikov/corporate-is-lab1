import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from PIL import Image
from rest_framework import serializers

from .models import BOOKS_ROOT_SLUG, BookEdition, Category, Product, ProductVariant
from .serializers import BookEditionSerializer, CategorySerializer, VariantSerializer

BOOK_FIELDS = ("author", "publisher", "year", "language", "binding", "isbn", "pages")
MAX_COVER_BYTES = 5 * 1024 * 1024
MAX_COVER_PIXELS = 20_000_000


class ManagerGenreWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)

    def validate_name(self, name):
        if not any(char.isalnum() for char in name):
            raise serializers.ValidationError("Введите название жанра.")
        return name


class ManagerBookSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    book = BookEditionSerializer(read_only=True, allow_null=True)
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "name",
            "slug",
            "sku",
            "description",
            "price",
            "old_price",
            "stock",
            "is_active",
            "image",
            "book",
            "variants",
        )
        read_only_fields = fields


@extend_schema_field(OpenApiTypes.BINARY)
class CoverField(serializers.FileField):
    def to_internal_value(self, data):
        upload = super().to_internal_value(data)
        if upload.size > MAX_COVER_BYTES:
            raise serializers.ValidationError("Файл обложки должен занимать не более 5 МБ.")
        try:
            with Image.open(upload, formats=["JPEG", "PNG"]) as image:
                if image.width * image.height > MAX_COVER_PIXELS:
                    raise serializers.ValidationError(
                        "Обложка слишком большая. Уменьшите её ширину или высоту в редакторе."
                    )
                image.verify()
            upload.seek(0)
            with Image.open(upload, formats=["JPEG", "PNG"]) as image:
                image.load()
                upload.name = "cover.jpg" if image.format == "JPEG" else "cover.png"
                upload.content_type = Image.MIME[image.format]
        except (
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombError,
        ) as error:
            raise serializers.ValidationError(
                "Загрузите читаемое изображение JPEG или PNG."
            ) from error
        finally:
            upload.seek(0)
        return upload


class ManagerBookWriteSerializer(serializers.ModelSerializer):
    author = serializers.CharField(max_length=200)
    publisher = serializers.CharField(max_length=200)
    year = serializers.IntegerField(min_value=1450, max_value=32767)
    language = serializers.CharField(max_length=80)
    binding = serializers.ChoiceField(choices=BookEdition.Binding.choices)
    isbn = serializers.CharField(max_length=40, allow_blank=True, required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.exclude(slug=BOOKS_ROOT_SLUG),
        error_messages={"does_not_exist": "Выберите жанр книги из списка."},
    )
    pages = serializers.IntegerField(min_value=1, max_value=2147483647)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    is_active = serializers.BooleanField(default=False)
    image = CoverField(required=False)

    class Meta:
        model = Product
        fields = (
            "category",
            "name",
            "slug",
            "sku",
            "description",
            "price",
            "old_price",
            "stock",
            "is_active",
            "image",
            *BOOK_FIELDS,
        )

    def validate(self, attrs):
        product = self.instance
        book = getattr(product, "book", None)
        errors = {}
        if product:
            for field in ("slug", "sku"):
                if field in attrs and attrs[field] != getattr(product, field):
                    errors[field] = "Идентификатор уже созданной книги менять нельзя."
            if product.variants.filter(is_default=False).exists():
                for field in ("price", "stock"):
                    if field in attrs and attrs[field] != getattr(product, field):
                        errors[field] = "Меняйте цену и остаток в складских вариантах книги."
        if not book:
            for field in BOOK_FIELDS:
                if field != "isbn" and field not in attrs:
                    errors[field] = "Заполните это поле для книжного издания."
        price = attrs.get("price", product.price if product else None)
        old_price = attrs.get("old_price", product.old_price if product else None)
        if price is not None and old_price is not None and old_price <= price:
            errors["old_price"] = "Старая цена должна быть больше текущей."
        try:
            BookEdition(isbn=attrs.get("isbn", book.isbn if book else "")).clean()
        except ValidationError as error:
            errors.update(error.message_dict)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def validate_isbn(self, isbn):
        return re.sub(r"[\s\-\u2010-\u2015]", "", isbn)

    def create(self, validated_data):
        return self.save_book(Product(), validated_data)

    def update(self, instance, validated_data):
        return self.save_book(instance, validated_data)

    @staticmethod
    def save_book(product, values):
        cover = values.pop("image", None)
        book_values = {name: values.pop(name) for name in BOOK_FIELDS if name in values}
        for name, value in values.items():
            setattr(product, name, value)
        product.save()
        if book_values:
            book, _ = BookEdition.objects.update_or_create(product=product, defaults=book_values)
            product.book = book
        if {"price", "stock"} & values.keys():
            product.variants.filter(is_default=True).update(
                price=product.price, stock=product.stock
            )
        if cover is not None:
            product.image = cover
            try:
                product.save(update_fields=["image"])
            except Exception:
                if product.image.name and product.image._committed:
                    product.image.storage.delete(product.image.name)
                raise
        return product


class ManagerVariantWriteSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = ProductVariant
        fields = ("price", "stock", "is_active")
