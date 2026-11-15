from django.db.models import Sum

from .services import get_cart


def cart(request):
    """Число товаров в корзине для шапки сайта."""
    current = get_cart(request)
    count = current.items.aggregate(n=Sum("quantity"))["n"] if current else 0
    return {"cart_count": count or 0}
