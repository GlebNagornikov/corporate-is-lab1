from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product
from .services import set_favorite as set_favorite
from .views import redirect_after_action


@login_required
def wishlist(request):
    return render(
        request,
        "catalog/wishlist.html",
        {"favorites": request.user.wishlist.select_related("product")},
    )


@login_required
@require_POST
def wishlist_change(request, pk):
    product = get_object_or_404(Product, pk=pk)
    enabled = request.POST.get("action") != "remove"
    set_favorite(request.user, product, enabled)
    if enabled:
        messages.success(request, f"«{product.name}» в избранном.")
    return redirect_after_action(request, "wishlist")


class FavoriteInput(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())


class WishlistAPI(APIView):
    serializer_class = FavoriteInput

    @extend_schema(
        responses=inline_serializer(
            name="WishlistEntry",
            fields={
                "product_id": serializers.IntegerField(),
                "product__name": serializers.CharField(),
                "product__slug": serializers.SlugField(),
                "product__is_active": serializers.BooleanField(),
            },
            many=True,
        )
    )
    def get(self, request):
        return Response(
            list(
                request.user.wishlist.order_by("pk").values(
                    "product_id", "product__name", "product__slug", "product__is_active"
                )
            )
        )

    @extend_schema(
        responses={
            201: inline_serializer("FavoriteResult", {"product_id": serializers.IntegerField()})
        }
    )
    def post(self, request):
        data = FavoriteInput(data=request.data)
        data.is_valid(raise_exception=True)
        item = set_favorite(request.user, data.validated_data["product"])
        return Response({"product_id": item.product_id}, status=201)

    @extend_schema(
        operation_id="wishlist_remove_body", request=FavoriteInput, responses={204: None}
    )
    def delete(self, request, pk=None):
        data = FavoriteInput(data={"product": pk or request.data.get("product")})
        data.is_valid(raise_exception=True)
        set_favorite(request.user, data.validated_data["product"], False)
        return Response(status=204)


class WishlistDetailAPI(WishlistAPI):
    http_method_names = ["delete", "options"]

    @extend_schema(operation_id="wishlist_remove_product", request=None, responses={204: None})
    def delete(self, request, pk=None):
        return super().delete(request, pk)


urlpatterns = [
    path("wishlist/", wishlist, name="wishlist"),
    path("wishlist/<int:pk>/", wishlist_change, name="wishlist-change"),
    path("api/wishlist/", WishlistAPI.as_view()),
    path("api/wishlist/<int:pk>/", WishlistDetailAPI.as_view()),
]
