from decimal import Decimal

from django.db import IntegrityError, transaction
from django.urls import path
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from accounts.manager_permissions import IsShopManager
from cart.services import get_cart
from config.api_docs import MANAGER_ACCESS_ERRORS

from .models import PromoCode
from .services import OrderError, get_valid_promo, promo_discount


class PromoCodeField(serializers.CharField):
    def to_internal_value(self, data):
        return super().to_internal_value(data).upper()


class PromoSelectionSerializer(serializers.Serializer):
    promo_code = PromoCodeField(max_length=30, allow_blank=True)


class PromoCheckSerializer(serializers.Serializer):
    code = PromoCodeField(max_length=30)
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )


class PromoQuoteSerializer(serializers.Serializer):
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(allow_null=True)


def quote_promo(code, subtotal):
    discount = Decimal("0")
    reason = None
    try:
        discount = promo_discount(get_valid_promo(code, subtotal=subtotal), subtotal)
    except OrderError as error:
        reason = str(error)
    return {"discount": discount, "total": subtotal - discount, "reason": reason}


class PromoCheckView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PromoCheckSerializer

    @extend_schema(
        description=(
            "Проверяет код без списания использования. Гость передаёт предварительную сумму "
            "книг в subtotal. Для покупателя сумма читается из его корзины. "
            "Причина неприменимости возвращается в reason."
        ),
        responses={200: PromoQuoteSerializer, 400: OpenApiResponse(description="Неверные данные.")},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subtotal = serializer.validated_data.get("subtotal")
        if request.user.is_authenticated:
            cart = get_cart(request)
            subtotal = cart.total if cart else Decimal("0")
        elif subtotal is None:
            raise serializers.ValidationError({"subtotal": "Укажите сумму книг в корзине."})
        quote = quote_promo(serializer.validated_data["code"], subtotal)
        return Response(PromoQuoteSerializer(quote).data)


class ManagerPromoSerializer(serializers.ModelSerializer):
    code = PromoCodeField(max_length=30)
    max_uses = serializers.IntegerField(
        min_value=1, max_value=2147483647, required=False, allow_null=True
    )

    class Meta:
        model = PromoCode
        fields = (
            "id",
            "code",
            "discount_percent",
            "minimum_subtotal",
            "valid_from",
            "valid_until",
            "max_uses",
            "used_count",
            "is_active",
        )
        read_only_fields = ("used_count", "is_active")

    def validate(self, attrs):
        if attrs["valid_until"] <= attrs["valid_from"]:
            raise serializers.ValidationError(
                {"valid_until": "Укажите дату позже начала действия."}
            )
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            if PromoCode.objects.filter(code=validated_data["code"]).exists():
                raise serializers.ValidationError(
                    {"code": "Такой промокод уже существует."}
                ) from None
            raise


class PromoPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    list=extend_schema(
        description="Список промокодов и число использований.",
        responses={200: ManagerPromoSerializer(many=True), **MANAGER_ACCESS_ERRORS},
    ),
    create=extend_schema(
        description="Создаёт промокод с заданным периодом действия и условиями.",
        responses={
            201: ManagerPromoSerializer,
            400: OpenApiResponse(description="Поля заполнены неверно или код уже существует."),
            **MANAGER_ACCESS_ERRORS,
        },
    ),
)
class ManagerPromoViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = PromoCode.objects.order_by("-pk")
    serializer_class = ManagerPromoSerializer
    pagination_class = PromoPagination
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    manager_permissions = {
        "list": ("orders.view_promocode",),
        "create": ("orders.view_promocode", "orders.add_promocode"),
        "deactivate": ("orders.view_promocode", "orders.change_promocode"),
    }

    @extend_schema(
        description="Деактивирует промокод и сохраняет историю его использований.",
        request=None,
        responses={
            204: None,
            404: OpenApiResponse(description="Промокод не найден."),
            **MANAGER_ACCESS_ERRORS,
        },
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        PromoCode.objects.filter(pk=self.get_object().pk).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


urlpatterns = [path("promo/check/", PromoCheckView.as_view(), name="api-promo-check")]
