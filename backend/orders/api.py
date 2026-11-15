from django.core.exceptions import ValidationError
from django.core.handlers.asgi import ASGIRequest
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.manager_permissions import IsShopManager
from cart.services import get_cart
from config.api_docs import MANAGER_ACCESS_ERRORS

from .events import order_events
from .models import Order
from .serializers import (
    CheckoutSerializer,
    OrderSerializer,
    SimulatedPaymentSerializer,
    StatusChangeSerializer,
)
from .services import (
    MAX_COPIES_PER_EDITION,
    OrderError,
    cancel_by_customer,
    change_status,
    place_order,
    simulate_payment,
)


class IsOrderManager(IsShopManager):
    message = "Менять статус заказов могут только менеджеры магазина с нужными правами."


ORDER_NOT_FOUND = OpenApiResponse(description="Заказ не найден.")


class OrderEventsNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        # Успешный ответ формируется как SSE, а ошибки DRF всегда возвращаются в JSON.
        return renderers[0], renderers[0].media_type


class OrderStatusMixin:
    @extend_schema(
        description="Меняет статус заказа по допустимым переходам. При отмене нужна причина.",
        request=StatusChangeSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(
                description="Недопустимый переход или отсутствует причина отмены."
            ),
            404: ORDER_NOT_FOUND,
            **MANAGER_ACCESS_ERRORS,
        },
    )
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


def orders_for_display():
    return (
        Order.objects.prefetch_related("items", "history__changed_by")
        .select_related("promo_code")
        .order_by("-created_at", "-pk")
    )


class OrderViewSet(
    OrderStatusMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]
    manager_permissions = {}

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        queryset = orders_for_display()
        if self.action not in {"cancel", "pay"} and self.request.user.has_perm("orders.view_order"):
            return queryset
        return queryset.filter(user=self.request.user)

    @extend_schema(
        description=(
            "Поток SSE доступен владельцу заказа по Bearer-токену. Событие order-changed "
            "при подключении и после изменения статуса предлагает заново прочитать карточку."
        ),
        responses={
            (200, "text/event-stream"): {"type": "string"},
            401: OpenApiResponse(description="Требуется действующий access-токен."),
            404: ORDER_NOT_FOUND,
            503: OpenApiResponse(description="Поток требует запуска Django под ASGI."),
        },
    )
    @action(
        detail=True,
        authentication_classes=[JWTAuthentication],
        content_negotiation_class=OrderEventsNegotiation,
        renderer_classes=[JSONRenderer],
        url_path="events",
    )
    def events(self, request, pk=None):
        if not pk or not pk.isdecimal():
            raise Http404
        order = get_object_or_404(Order.objects.only("pk"), pk=pk, user_id=request.user.pk)
        if not isinstance(request._request, ASGIRequest):
            return Response({"detail": "Поток доступен под ASGI."}, status=503)
        return StreamingHttpResponse(
            order_events(order.pk, request.user.pk, request.user.password, request.auth["exp"]),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @extend_schema(
        description=(
            f"Оформляет текущую корзину. Лимит — {MAX_COPIES_PER_EDITION} экземпляров "
            "одного издания суммарно по всем его вариантам. Остатки и цены проверяются на сервере."
        ),
        request=CheckoutSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(
                response={
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["detail"],
                            "properties": {"detail": {"type": "string"}},
                        },
                        {
                            "type": "object",
                            "additionalProperties": {"type": "array", "items": {"type": "string"}},
                        },
                    ],
                },
                description="Ошибка оформления в detail или список ошибок по имени поля.",
                examples=[
                    OpenApiExample(
                        "Превышен лимит экземпляров",
                        value={
                            "detail": "«Чистый код»: в одном заказе можно купить не больше "
                            f"{MAX_COPIES_PER_EDITION} экземпляров издания с учётом всех "
                            "вариантов. В корзине 6."
                        },
                        status_codes=[400],
                    ),
                    OpenApiExample(
                        "Остаток изменился",
                        value={"detail": "Товара «Чистый код» осталось только 1 шт."},
                        status_codes=[400],
                    ),
                    OpenApiExample(
                        "Ошибка поля",
                        value={
                            "phone": [
                                "Введите российский номер телефона, например +7 913 123-45-67."
                            ]
                        },
                        status_codes=[400],
                    ),
                ],
            ),
        },
    )
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
        order = self.get_object()
        payment = SimulatedPaymentSerializer(data=request.data)
        payment.is_valid(raise_exception=True)
        try:
            order = simulate_payment(order, request.user, payment.validated_data["outcome"])
        except ValidationError as error:
            raise serializers.ValidationError({"detail": error.messages[0]}) from error
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(self.get_serializer(order).data)


@extend_schema_view(
    list=extend_schema(
        description="Заказы магазина с пагинацией и фильтром по статусу.",
        responses={200: OrderSerializer(many=True), **MANAGER_ACCESS_ERRORS},
    ),
    retrieve=extend_schema(
        description="Карточка заказа и история его статусов для сотрудника.",
        responses={200: OrderSerializer, 404: ORDER_NOT_FOUND, **MANAGER_ACCESS_ERRORS},
    ),
)
class ManagerOrderViewSet(OrderStatusMixin, viewsets.ReadOnlyModelViewSet):
    queryset = orders_for_display()
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    manager_permissions = {
        "list": ("orders.view_order",),
        "retrieve": ("orders.view_order",),
        "set_status": ("orders.view_order", "orders.change_order"),
    }


router = SimpleRouter()
router.register("orders", OrderViewSet, basename="order")
urlpatterns = router.urls
