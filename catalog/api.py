from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .filters import ProductFilter
from .models import Category, Product, Review
from .serializers import CategorySerializer, ProductSerializer, ReviewSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.select_related("parent")
    serializer_class = CategorySerializer
    lookup_field = "slug"
    pagination_class = None


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category__parent")
            .with_rating()
            .order_by("-created_at")
        )

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[permissions.IsAuthenticatedOrReadOnly],
    )
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            reviews = product.reviews.filter(is_published=True).select_related("author")
            return Response(ReviewSerializer(reviews, many=True).data)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Review.objects.filter(product=product, author=request.user).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв на этот товар.")
        serializer.save(product=product, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
