from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from catalog.models import Product, ProductVariant

from .services import add_to_cart, get_cart, merge_guest_items, remove_from_cart, set_quantity


class CartItemSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(allow_null=True)
    variant_name = serializers.CharField(source="variant.name", default="")
    is_default_variant = serializers.BooleanField(source="variant.is_default", default=True)
    product_id = serializers.IntegerField(source="product.pk")
    name = serializers.CharField(source="product.name")
    slug = serializers.CharField(source="product.slug")
    image = serializers.ImageField(source="product.image", allow_null=True)
    stock = serializers.IntegerField(source="available_stock")
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


class MergeLineSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    variant = serializers.IntegerField(min_value=1, required=False)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class MergeSerializer(serializers.Serializer):
    items = MergeLineSerializer(many=True)


class VariantQuerySerializer(serializers.Serializer):
    variant = serializers.IntegerField(min_value=1, required=False)


def cart_response(request, cart):
    cart = type(cart).objects.prefetch_related("items__product", "items__variant").get(pk=cart.pk)
    return Response(CartSerializer(cart, context={"request": request}).data)


class CartView(GenericAPIView):
    serializer_class = CartSerializer

    def get(self, request):
        return cart_response(request, get_cart(request, create=True))


class CartItemsView(GenericAPIView):
    serializer_class = AddItemSerializer

    @extend_schema(responses={200: CartSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
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
        return cart_response(request, cart)


@extend_schema(parameters=[VariantQuerySerializer])
class CartItemDetailView(GenericAPIView):
    serializer_class = QuantitySerializer

    def get_variant_id(self):
        serializer = VariantQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("variant")

    @extend_schema(responses={200: CartSerializer})
    def patch(self, request, product_id: int):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=product_id)
        variant_id = self.get_variant_id()
        variant = (
            get_object_or_404(ProductVariant, pk=variant_id, product=product)
            if variant_id is not None
            else None
        )
        cart = get_cart(request, create=True)
        try:
            set_quantity(cart, product, serializer.validated_data["quantity"], variant=variant)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return cart_response(request, cart)

    @extend_schema(request=None, responses={200: CartSerializer})
    def delete(self, request, product_id: int):
        variant_id = self.get_variant_id()
        cart = get_cart(request, create=True)
        remove_from_cart(cart, product_id, variant_id)
        return cart_response(request, cart)


class CartMergeView(GenericAPIView):
    """Переносит доступные товары гостевой корзины из браузера."""

    serializer_class = MergeSerializer

    @extend_schema(responses={200: CartSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = merge_guest_items(request.user, serializer.validated_data["items"])
        return cart_response(request, cart)


urlpatterns = [
    path("cart/", CartView.as_view(), name="api-cart"),
    path("cart/items/", CartItemsView.as_view(), name="api-cart-items"),
    path("cart/items/<int:product_id>/", CartItemDetailView.as_view(), name="api-cart-item"),
    path("cart/merge/", CartMergeView.as_view(), name="api-cart-merge"),
]
