from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter

from cart.services import get_cart

from .models import Order
from .serializers import (
    CheckoutSerializer,
    OrderSerializer,
    SimulatedPaymentSerializer,
    StatusChangeSerializer,
)
from .services import OrderError, cancel_by_customer, change_status, place_order, simulate_payment


class IsOrderManager(permissions.BasePermission):
    message = "Менять статус заказов могут только менеджеры магазина."

    def has_permission(self, request, view):
        return request.user.has_perm("orders.change_order")


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        queryset = Order.objects.prefetch_related("items", "history__changed_by").select_related(
            "promo_code"
        )
        if self.request.user.has_perm("orders.view_order"):
            return queryset
        return queryset.filter(user=self.request.user)

    @extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
    def create(self, request):
        checkout = CheckoutSerializer(data=request.data)
        checkout.is_valid(raise_exception=True)
        cart = get_cart(request)
        if cart is None:
            raise serializers.ValidationError({"detail": "Корзина пуста."})
        try:
            order = place_order(user=request.user, cart=cart, **checkout.validated_data)
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            order = cancel_by_customer(self.get_object(), request.user)
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(self.get_serializer(order).data)

    @extend_schema(
        description="Учебная оплата нового заказа. Доступна владельцу заказа.",
        request=SimulatedPaymentSerializer,
        responses=OrderSerializer,
        examples=[
            OpenApiExample("Успешная оплата", value={"outcome": "success"}, request_only=True)
        ],
    )
    @action(detail=True, methods=["post"], url_path="simulate-payment")
    def pay(self, request, pk=None):
        payment = SimulatedPaymentSerializer(data=request.data)
        payment.is_valid(raise_exception=True)
        try:
            order = simulate_payment(
                self.get_object(), request.user, payment.validated_data["outcome"]
            )
        except ValidationError as error:
            raise serializers.ValidationError({"detail": error.messages[0]}) from error
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(self.get_serializer(order).data)

    @extend_schema(request=StatusChangeSerializer, responses=OrderSerializer)
    @action(
        detail=True,
        methods=["post"],
        url_path="status",
        permission_classes=[permissions.IsAuthenticated, IsOrderManager],
    )
    def set_status(self, request, pk=None):
        data = StatusChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            order = change_status(
                self.get_object(),
                data.validated_data["status"],
                by=request.user,
                comment=data.validated_data.get("comment", ""),
            )
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(self.get_serializer(order).data)


router = SimpleRouter()
router.register("orders", OrderViewSet, basename="order")
urlpatterns = router.urls
