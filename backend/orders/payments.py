import hmac
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.views import APIView

from .models import Order
from .services import OrderError
from .services import apply_payment as apply_payment
from .services import begin_payment as begin_payment
from .services import signature as signature


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


class PaymentWebhookInputSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    outcome = serializers.ChoiceField(choices=["success", "failed"])


@csrf_exempt
@require_POST
def webhook(request):
    if not hmac.compare_digest(
        signature(request.body).encode(), request.headers.get("X-Payment-Signature", "").encode()
    ):
        return JsonResponse({"error": "Неверная подпись"}, status=403)
    try:
        payload = PaymentWebhookInputSerializer(data=json.loads(request.body))
        if not payload.is_valid():
            return JsonResponse({"error": "Неверные данные платежа."}, status=400)
        payment = apply_payment(**payload.validated_data)
    except (ValueError, RecursionError, ValidationError, OrderError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"status": payment.status})


class PaymentWebhookAPI(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        description="HMAC-SHA256 от точного тела. Неверная подпись — 403; успех идемпотентен.",
        parameters=[
            OpenApiParameter("X-Payment-Signature", str, OpenApiParameter.HEADER, required=True)
        ],
        request=PaymentWebhookInputSerializer,
        responses=inline_serializer(
            name="PaymentWebhookResult", fields={"status": serializers.CharField()}
        ),
    )
    def post(self, request):
        return webhook(request._request)


urlpatterns = [
    path("payments/gateway/<int:pk>/", gateway, name="payment-gateway"),
    path("payments/webhook/", PaymentWebhookAPI.as_view(), name="payment-webhook"),
]
