from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Address

from .models import Order, OrderItem, OrderStatusLog
from .validators import normalize_phone


class OrderItemSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "product",
            "product_name",
            "variant",
            "variant_name",
            "price",
            "quantity",
            "total",
        ]


class OrderStatusLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField()

    class Meta:
        model = OrderStatusLog
        fields = ["from_status", "to_status", "changed_by", "comment", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderStatusLogSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    promo_code = serializers.StringRelatedField(allow_null=True)
    allowed_transitions = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_pay = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "status_display",
            "full_name",
            "phone",
            "email",
            "delivery_method",
            "address",
            "comment",
            "promo_code",
            "subtotal",
            "discount",
            "delivery_cost",
            "total",
            "items",
            "history",
            "created_at",
            "allowed_transitions",
            "can_cancel",
            "can_pay",
        ]
        read_only_fields = fields

    def _user(self):
        request = self.context.get("request")
        return request.user if request else None

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(Order.Status.choices)))
    def get_allowed_transitions(self, order):
        user = self._user()
        if user is None or not user.has_perm("orders.change_order"):
            return []
        # Только платёжный шлюз может перевести заказ в статус PAID.
        return sorted(Order.TRANSITIONS[order.status] - {Order.Status.PAID})

    def _is_owner(self, order):
        user = self._user()
        return bool(user and user.is_authenticated and order.user_id == user.pk)

    def get_can_cancel(self, order) -> bool:
        return self._is_owner(order) and order.can_be_cancelled_by_customer

    def get_can_pay(self, order) -> bool:
        return self._is_owner(order) and order.can_be_paid


class CheckoutSerializer(serializers.ModelSerializer):
    address_book = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all(), required=False
    )
    promo_code = serializers.CharField(max_length=30, required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = [
            "full_name",
            "address_book",
            "phone",
            "email",
            "delivery_method",
            "address",
            "comment",
            "promo_code",
        ]
        extra_kwargs = {"delivery_method": {"required": True}}

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["status"] == Order.Status.CANCELLED and not attrs.get("comment"):
            raise serializers.ValidationError({"comment": "Укажите причину отмены."})
        return attrs


class SimulatedPaymentSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["success", "failed"])
