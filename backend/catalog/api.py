from django.db.models import Case, Exists, OuterRef, Value, When
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .filters import ProductFilter
from .models import Category, Product, Review
from .pagination import ProductPagination, ReviewPagination
from .reviews import ReviewError, create_review, review_block_reason
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductSerializer,
    ReviewEligibilitySerializer,
    ReviewSerializer,
)

EDITORIAL_SLUGS = (
    "war-of-worlds-1898",
    "wonderful-wizard-oz-1900",
    "anne-green-gables-1908",
    "peter-pan-kensington-1906",
    "story-amulet-1906",
)


def storefront_products():
    return (
        Product.objects.active()
        .select_related("category__parent", "book")
        .with_rating()
        .prefetch_related("variants")
    )


@extend_schema_view(
    get=extend_schema(description="До четырёх доступных карточек из подборки «Выбор редакции»."),
)
class EditorialView(generics.ListAPIView):
    queryset = Product.objects.none()
    serializer_class = ProductSerializer
    pagination_class = None
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        editorial_order = Case(
            *(When(slug=slug, then=Value(index)) for index, slug in enumerate(EDITORIAL_SLUGS))
        )
        return storefront_products().filter(slug__in=EDITORIAL_SLUGS).order_by(editorial_order)[:4]


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
        queryset = storefront_products().order_by("-created_at", "pk")
        return queryset.prefetch_related("images") if self.action == "retrieve" else queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return super().get_serializer_class()

    @extend_schema(
        methods=["GET"],
        description="Опубликованные отзывы об издании, от новых к старым, по 5 на страницу.",
        responses=ReviewSerializer(many=True),
    )
    @extend_schema(
        methods=["POST"],
        description="Принимает один отзыв от покупателя с доставленным заказом на издание.",
        request=ReviewSerializer,
        responses={
            201: ReviewSerializer,
            400: OpenApiResponse(description="Неверные поля, нет доставленной покупки или дубль."),
            401: OpenApiResponse(description="Требуется вход."),
        },
    )
    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[permissions.IsAuthenticatedOrReadOnly],
        pagination_class=ReviewPagination,
        filter_backends=[],
    )
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            reviews = product.reviews.filter(status=Review.Status.APPROVED).select_related("author")
            page = self.paginate_queryset(reviews)
            return self.get_paginated_response(ReviewSerializer(page, many=True).data)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = create_review(
                product=product, author=request.user, **serializer.validated_data
            )
        except ReviewError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Персональное право на отзыв и состояние собственного отзыва.",
        responses={
            200: ReviewEligibilitySerializer,
            401: OpenApiResponse(description="Требуется вход."),
            404: OpenApiResponse(description="Издание не найдено."),
        },
    )
    @action(
        detail=True,
        url_path="review-eligibility",
        permission_classes=[permissions.IsAuthenticated],
        filter_backends=[],
        pagination_class=None,
    )
    @method_decorator(never_cache)
    def review_eligibility(self, request, slug=None):
        reason = review_block_reason(self.get_object(), request.user)
        result = ReviewEligibilitySerializer({"can_review": not reason, "message": reason})
        return Response(result.data)


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet, basename="product")

urlpatterns = [path("editorial/", EditorialView.as_view(), name="catalog-editorial"), *router.urls]
