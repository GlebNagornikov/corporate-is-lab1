from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product, ProductVariant

from .services import add_to_cart, get_cart, set_quantity


class CartItemSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(allow_null=True)
    variant_name = serializers.CharField(source="variant.name", default="")
    product_id = serializers.IntegerField(source="product.pk")
    name = serializers.CharField(source="product.name")
    price = serializers.DecimalField(source="unit_price", max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class AddItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.active())
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(is_active=True), required=False
    )
    quantity = serializers.IntegerField(min_value=1, default=1)


class QuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


def cart_response(cart):
    cart = type(cart).objects.prefetch_related("items__product", "items__variant").get(pk=cart.pk)
    return Response(CartSerializer(cart).data)


class CartView(APIView):
    serializer_class = CartSerializer

    def get(self, request):
        return cart_response(get_cart(request, create=True))


class CartItemsView(APIView):
    serializer_class = CartSerializer

    @extend_schema(request=AddItemSerializer, responses=CartSerializer)
    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_cart(request, create=True)
        try:
            add_to_cart(
                cart,
                serializer.validated_data["product"],
                serializer.validated_data["quantity"],
                variant=serializer.validated_data.get("variant"),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return cart_response(cart)


class CartItemDetailView(APIView):
    serializer_class = CartSerializer

    @extend_schema(request=QuantitySerializer, responses=CartSerializer)
    def patch(self, request, product_id):
        serializer = QuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_cart(request, create=True)
        product = get_object_or_404(Product, pk=product_id)
        variant = (
            get_object_or_404(ProductVariant, pk=request.query_params["variant"], product=product)
            if request.query_params.get("variant")
            else None
        )
        try:
            set_quantity(cart, product, serializer.validated_data["quantity"], variant=variant)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return cart_response(cart)

    def delete(self, request, product_id):
        cart = get_cart(request, create=True)
        rows = cart.items.filter(product_id=product_id)
        if request.query_params.get("variant"):
            rows = rows.filter(variant_id=request.query_params["variant"])
        rows.delete()
        return cart_response(cart)


urlpatterns = [
    path("cart/", CartView.as_view(), name="api-cart"),
    path("cart/items/", CartItemsView.as_view(), name="api-cart-items"),
    path("cart/items/<int:product_id>/", CartItemDetailView.as_view(), name="api-cart-item"),
]
