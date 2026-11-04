from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.views.decorators.http import require_POST

from .models import Product, StockSubscription


@transaction.atomic
def subscribe(product, email):
    product = Product.objects.select_for_update().get(pk=product.pk)
    if product.stock > 0 or not product.is_active:
        raise ValidationError("Подписка доступна только для отсутствующего товара.")
    email = email.strip().lower()
    validate_email(email)
    subscription, _ = StockSubscription.objects.update_or_create(
        product=product, email=email, defaults={"completed": False}
    )
    return subscription


def deliver_restock(product_id):
    for pk in StockSubscription.objects.filter(product_id=product_id, completed=False).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            subscription = (
                StockSubscription.objects.select_for_update().select_related("product").get(pk=pk)
            )
            if subscription.completed:
                continue
            product = subscription.product
            send_mail(
                f"В наличии: {product.name}",
                f"Товар снова в продаже: {settings.SITE_URL}{product.get_absolute_url()}",
                None,
                [subscription.email],
            )
            subscription.completed = True
            subscription.save(update_fields=["completed"])


def queue_restock(product_id):
    transaction.on_commit(lambda: deliver_restock(product_id))


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
