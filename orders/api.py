from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter

from cart.services import get_cart

from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer, StatusChangeSerializer
from .services import OrderError, cancel_by_customer, change_status, place_order


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
        queryset = Order.objects.prefetch_related("items", "history__changed_by").select_related(
            "promo_code"
        )
        if self.request.user.has_perm("orders.view_order"):
            return queryset
        return queryset.filter(user=self.request.user)

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
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            order = cancel_by_customer(self.get_object(), request.user)
        except OrderError as error:
            raise serializers.ValidationError({"detail": str(error)}) from error
        return Response(OrderSerializer(order).data)

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
        return Response(OrderSerializer(order).data)


router = SimpleRouter()
router.register("orders", OrderViewSet, basename="order")
urlpatterns = router.urls
