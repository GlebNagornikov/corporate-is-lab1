import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Order, Payment
from .services import OrderError, change_status


def signature(body):
    return hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


@transaction.atomic
def begin_payment(order, user):
    order = get_object_or_404(Order.objects.select_for_update(), pk=order.pk, user=user)
    if order.status != Order.Status.NEW:
        raise ValidationError("Оплатить можно только новый заказ.")
    return Payment.objects.create(order=order, amount=order.total)


@transaction.atomic
def apply_payment(payment_id, outcome):
    # The order is always locked before the payment, matching other order workflows.
    payment = get_object_or_404(Payment, pk=payment_id)
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != "pending":
        return payment
    if outcome == "success":
        if order.status != Order.Status.NEW or payment.amount != order.total:
            raise ValidationError("Заказ уже обработан или сумма изменилась.")
        change_status(
            order,
            Order.Status.PAID,
            by=order.user,
            comment="Подтверждено платёжным шлюзом",
            payment_verified=True,
        )
    payment.status = outcome
    payment.save(update_fields=["status"])
    return payment


@login_required
def gateway(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    context = {"order": order}
    if request.method == "POST":
        outcome = request.POST.get("outcome")
        if outcome not in {"success", "failed"}:
            return JsonResponse({"error": "Неверный результат"}, status=400)
        try:
            payment = begin_payment(order, request.user)
        except ValidationError as error:
            return JsonResponse({"error": error.messages}, status=400)
        payload = json.dumps({"payment_id": str(payment.pk), "outcome": outcome})
        context.update(payload=payload, signature=signature(payload.encode()))
    return render(request, "orders/gateway.html", context)


@csrf_exempt
@require_POST
def webhook(request):
    if not hmac.compare_digest(
        signature(request.body), request.headers.get("X-Payment-Signature", "")
    ):
        return JsonResponse({"error": "Неверная подпись"}, status=403)
    try:
        payload = json.loads(request.body)
        payment_id = uuid.UUID(payload["payment_id"])
        outcome = payload["outcome"]
        if outcome not in {"success", "failed"}:
            raise ValueError
        payment = apply_payment(payment_id, outcome)
    except (ValueError, TypeError, KeyError, ValidationError, OrderError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"status": payment.status})


urlpatterns = [
    path("payments/gateway/<int:pk>/", gateway, name="payment-gateway"),
    path("payments/webhook/", webhook, name="payment-webhook"),
]
