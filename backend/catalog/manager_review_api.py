from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from accounts.manager_permissions import IsShopManager
from config.api_docs import MANAGER_ACCESS_ERRORS

from .models import Review
from .reviews import ReviewError, moderate_review
from .serializers import ReviewSerializer


class ReviewQueuePagination(PageNumberPagination):
    page_size = 20


class ManagerReviewSerializer(ReviewSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.SlugField(source="product.slug", read_only=True)

    class Meta(ReviewSerializer.Meta):
        fields = [*ReviewSerializer.Meta.fields, "product_name", "product_slug"]


class ReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[Review.Status.APPROVED, Review.Status.REJECTED],
        help_text="Одобрить (approved) или отклонить (rejected).",
    )


@extend_schema_view(
    list=extend_schema(
        description="Очередь отзывов на модерации, от старых к новым.",
        responses={200: ManagerReviewSerializer(many=True), **MANAGER_ACCESS_ERRORS},
    ),
)
class ManagerReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Review.objects.select_related("author", "product").order_by("created_at", "pk")
    serializer_class = ManagerReviewSerializer
    pagination_class = ReviewQueuePagination
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    manager_permissions = {
        "list": ("catalog.view_review",),
        "moderate": ("catalog.view_review", "catalog.change_review"),
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            return queryset.filter(status=Review.Status.PENDING)
        return queryset

    @extend_schema(
        description="Записывает решение по отзыву, который ещё ожидает модерации.",
        request=ReviewDecisionSerializer,
        responses={
            204: None,
            400: OpenApiResponse(description="Неверное решение или отзыв уже обработан."),
            404: OpenApiResponse(description="Отзыв не найден."),
            **MANAGER_ACCESS_ERRORS,
        },
    )
    @action(detail=True, methods=["post"])
    def moderate(self, request, pk=None):
        serializer = ReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            moderate_review(review_id=self.get_object().pk, **serializer.validated_data)
        except Review.DoesNotExist:
            raise NotFound("Отзыв не найден.") from None
        except ReviewError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(status=status.HTTP_204_NO_CONTENT)
