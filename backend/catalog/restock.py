from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.views.decorators.http import require_POST

from .models import Product
from .services import deliver_restock as deliver_restock
from .services import queue_restock as queue_restock
from .services import subscribe as subscribe


class SubscriptionForm(forms.Form):
    email = forms.EmailField()


@require_POST
def subscribe_view(request, pk):
    product = get_object_or_404(Product.objects.active(), pk=pk)
    form = SubscriptionForm(
        {
            "email": request.POST.get("email")
            or (request.user.email if request.user.is_authenticated else "")
        }
    )
    if form.is_valid():
        try:
            subscribe(product, form.cleaned_data["email"])
            messages.success(request, "Сообщим, когда товар появится в наличии.")
        except ValidationError as error:
            messages.error(request, error.messages[0])
    else:
        messages.error(request, "Укажите корректный email.")
    return redirect(product)


urlpatterns = [path("restock/<int:pk>/", subscribe_view, name="restock")]
