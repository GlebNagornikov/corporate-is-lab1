from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product

from .services import add_to_cart, get_cart, set_quantity


class CartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(source="product.pk")
    name = serializers.CharField(source="product.name")
    price = serializers.DecimalField(source="product.price", max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class AddItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.active())
    quantity = serializers.IntegerField(min_value=1, default=1)


class QuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


def cart_response(cart):
    cart = type(cart).objects.prefetch_related("items__product").get(pk=cart.pk)
    return Response(CartSerializer(cart).data)


class CartView(APIView):
    def get(self, request):
        return cart_response(get_cart(request, create=True))


class CartItemsView(APIView):
    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_cart(request, create=True)
        try:
            add_to_cart(
                cart, serializer.validated_data["product"], serializer.validated_data["quantity"]
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return cart_response(cart)


class CartItemDetailView(APIView):
    def patch(self, request, product_id):
        serializer = QuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_cart(request, create=True)
        product = get_object_or_404(Product, pk=product_id)
        try:
            set_quantity(cart, product, serializer.validated_data["quantity"])
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return cart_response(cart)

    def delete(self, request, product_id):
        cart = get_cart(request, create=True)
        cart.items.filter(product_id=product_id).delete()
        return cart_response(cart)


urlpatterns = [
    path("cart/", CartView.as_view(), name="api-cart"),
    path("cart/items/", CartItemsView.as_view(), name="api-cart-items"),
    path("cart/items/<int:product_id>/", CartItemDetailView.as_view(), name="api-cart-item"),
]
