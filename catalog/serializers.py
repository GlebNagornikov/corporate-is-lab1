from rest_framework import serializers

from .models import Category, Product, ProductVariant, Review


class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent"]


class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "name", "sku", "price", "stock", "is_active", "is_default"]


class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "sku",
            "category",
            "description",
            "attributes",
            "variants",
            "price",
            "old_price",
            "discount_percent",
            "stock",
            "in_stock",
            "image",
            "rating",
            "reviews_count",
        ]

    def get_rating(self, product) -> float | None:
        return round(product.rating, 1) if product.rating is not None else None


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "author", "rating", "text", "created_at"]
