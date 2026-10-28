from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Product

from .services import add_to_cart, get_cart, set_quantity


def cart_detail(request):
    cart = get_cart(request)
    items = cart.items.select_related("product") if cart else []
    total = sum((item.total for item in items), start=0)
    return render(request, "cart/cart_detail.html", {"items": items, "total": total})


def _quantity(request):
    try:
        return max(int(request.POST.get("quantity", 1)), 0)
    except ValueError:
        return 1


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        added = add_to_cart(get_cart(request, create=True), product, _quantity(request))
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        if added:
            messages.success(request, f"«{product.name}» в корзине: {added} шт.")
        else:
            messages.error(request, f"«{product.name}» нет в наличии.")
    return redirect(request.POST.get("next") or "cart:detail")


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = get_cart(request)
    if cart:
        try:
            set_quantity(cart, product, _quantity(request))
        except ValidationError as error:
            messages.error(request, error.messages[0])
    return redirect("cart:detail")
