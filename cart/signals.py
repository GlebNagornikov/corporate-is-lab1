from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Cart
from .services import CART_SESSION_KEY, merge_carts


@receiver(user_logged_in)
def merge_guest_cart(sender, request, user, **kwargs):
    if request is None or not hasattr(request, "session"):
        return
    cart_id = request.session.pop(CART_SESSION_KEY, None)
    guest_cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if guest_cart:
        skipped = merge_carts(guest_cart, Cart.objects.get_or_create(user=user)[0])
        if skipped and hasattr(request, "_messages"):
            messages.warning(
                request,
                "Недоступные товары не перенесены в корзину: " + ", ".join(skipped),
            )
