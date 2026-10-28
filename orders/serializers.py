from rest_framework import serializers

from .models import Order, OrderItem, OrderStatusLog


class OrderItemSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product", "product_name", "price", "quantity", "total"]


class OrderStatusLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField()

    class Meta:
        model = OrderStatusLog
        fields = ["from_status", "to_status", "changed_by", "comment", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderStatusLogSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    promo_code = serializers.StringRelatedField()

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
        ]
        read_only_fields = fields


class CheckoutSerializer(serializers.ModelSerializer):
    promo_code = serializers.CharField(max_length=30, required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = [
            "full_name",
            "phone",
            "email",
            "delivery_method",
            "address",
            "comment",
            "promo_code",
        ]


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)
