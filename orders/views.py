from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView

from cart.services import get_cart

from .forms import CheckoutForm
from .models import Order
from .services import OrderError, cancel_by_customer, place_order


class CheckoutView(LoginRequiredMixin, FormView):
    form_class = CheckoutForm
    template_name = "orders/checkout.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.cart = get_cart(request)
            if self.cart is None or not self.cart.items.exists():
                messages.info(request, "Корзина пуста.")
                return redirect("cart:detail")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        user = self.request.user
        return {"full_name": user.get_full_name(), "email": user.email, "phone": user.phone}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = self.cart.items.select_related("product")
        return context

    def form_valid(self, form):
        try:
            order = place_order(user=self.request.user, cart=self.cart, **form.cleaned_data)
        except OrderError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, f"Заказ №{order.pk} оформлен. Письмо отправлено на почту.")
        return redirect(order)


class OrderListView(LoginRequiredMixin, ListView):
    template_name = "orders/order_list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items", "history")


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        cancel_by_customer(order, request.user)
    except OrderError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Заказ №{order.pk} отменён.")
    return redirect(order)
