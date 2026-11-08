from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .filters import ProductFilter
from .models import Category, Product, Review
from .pagination import ProductPagination
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductSerializer,
    ReviewSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.select_related("parent")
    serializer_class = CategorySerializer
    lookup_field = "slug"
    pagination_class = None
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        """Категории активных товаров и их родительские категории."""
        active_products = Product.objects.active().filter(category_id=OuterRef("pk"))
        categories = self.get_queryset().annotate(has_active_products=Exists(active_products))
        by_id = {category.pk: category for category in categories}
        visible_ids = set()
        for category in by_id.values():
            if not category.has_active_products:
                continue
            category_id = category.pk
            while category_id is not None and category_id not in visible_ids:
                visible_ids.add(category_id)
                category_id = by_id[category_id].parent_id
        visible = [category for category in by_id.values() if category.pk in visible_ids]
        return Response(self.get_serializer(visible, many=True).data)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        queryset = (
            Product.objects.active()
            .select_related("category__parent", "book")
            .with_rating()
            .prefetch_related("variants")
            .order_by("-created_at", "pk")
        )
        return queryset.prefetch_related("images") if self.action == "retrieve" else queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return super().get_serializer_class()

    @extend_schema(methods=["GET"], responses=ReviewSerializer(many=True), filters=False)
    @extend_schema(methods=["POST"], request=ReviewSerializer, responses={201: ReviewSerializer})
    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[permissions.IsAuthenticatedOrReadOnly],
        pagination_class=None,
    )
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            reviews = product.reviews.filter(is_published=True).select_related("author")
            return Response(ReviewSerializer(reviews, many=True).data)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(product=product, author=request.user)
        except IntegrityError as error:
            if not Review.objects.filter(product=product, author=request.user).exists():
                raise
            raise serializers.ValidationError("Вы уже оставили отзыв на этот товар.") from error
        return Response(serializer.data, status=status.HTTP_201_CREATED)


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
