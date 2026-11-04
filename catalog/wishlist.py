from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_POST
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product, WishlistItem


def set_favorite(user, product, enabled=True):
    if enabled:
        return WishlistItem.objects.get_or_create(user=user, product=product)[0]
    WishlistItem.objects.filter(user=user, product=product).delete()


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
    set_favorite(
        request.user, get_object_or_404(Product, pk=pk), request.POST.get("action") != "remove"
    )
    return redirect("wishlist")


class FavoriteInput(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())


class WishlistAPI(APIView):
    def get(self, request):
        return Response(
            list(
                request.user.wishlist.order_by("pk").values(
                    "product_id", "product__name", "product__is_active"
                )
            )
        )

    def post(self, request):
        data = FavoriteInput(data=request.data)
        data.is_valid(raise_exception=True)
        item = set_favorite(request.user, data.validated_data["product"])
        return Response({"product_id": item.product_id}, status=201)

    def delete(self, request, pk=None):
        data = FavoriteInput(data={"product": pk or request.data.get("product")})
        data.is_valid(raise_exception=True)
        set_favorite(request.user, data.validated_data["product"], False)
        return Response(status=204)


urlpatterns = [
    path("wishlist/", wishlist, name="wishlist"),
    path("wishlist/<int:pk>/", wishlist_change, name="wishlist-change"),
    path("api/wishlist/", WishlistAPI.as_view()),
    path("api/wishlist/<int:pk>/", WishlistAPI.as_view()),
]
