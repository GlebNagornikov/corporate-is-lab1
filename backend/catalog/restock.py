from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Product, RestockNotification
from .services import deliver_restock as deliver_restock
from .services import queue_restock as queue_restock
from .services import subscribe as subscribe
from .services import subscribe_personally


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


class RestockSubscriptionSerializer(serializers.Serializer):
    subscribed = serializers.BooleanField()


class RestockSubscriptionAPI(APIView):
    @extend_schema(responses=RestockSubscriptionSerializer, summary="Проверить личную подписку")
    def get(self, request, pk):
        product = get_object_or_404(Product.objects.active(), pk=pk)
        subscribed = RestockNotification.objects.filter(
            product=product, user=request.user, notified_at=None
        ).exists()
        return Response({"subscribed": subscribed})

    @extend_schema(
        request=None,
        responses={
            200: RestockSubscriptionSerializer,
            400: OpenApiResponse(description="Издание уже есть в наличии."),
            404: OpenApiResponse(description="Издание не найдено в каталоге."),
        },
        summary="Подписаться на поступление издания",
    )
    def post(self, request, pk):
        try:
            subscribe_personally(pk, request.user)
        except Product.DoesNotExist as error:
            raise NotFound("Издание не найдено в каталоге.") from error
        except ValidationError as error:
            raise serializers.ValidationError({"detail": error.messages[0]}) from error
        return Response({"subscribed": True})


class RestockNotificationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    product_slug = serializers.SlugField(source="product.slug")
    product_is_active = serializers.BooleanField(source="product.is_active")
    notified_at = serializers.DateTimeField()
    read_at = serializers.DateTimeField(allow_null=True)

    class Meta:
        model = RestockNotification
        fields = (
            "id",
            "product_name",
            "product_slug",
            "product_is_active",
            "notified_at",
            "read_at",
        )


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField(min_value=0)


def personal_notifications(user):
    return RestockNotification.objects.filter(user=user, notified_at__isnull=False)


class NotificationsAPI(APIView):
    @extend_schema(responses=RestockNotificationSerializer(many=True), summary="Мои уведомления")
    def get(self, request):
        notifications = personal_notifications(request.user).select_related("product")
        return Response(
            RestockNotificationSerializer(
                notifications.order_by("-notified_at", "-pk"), many=True
            ).data
        )


class UnreadNotificationsAPI(APIView):
    @extend_schema(responses=UnreadCountSerializer, summary="Число непрочитанных уведомлений")
    def get(self, request):
        return Response(
            {"unread_count": personal_notifications(request.user).filter(read_at=None).count()}
        )

    @extend_schema(request=None, responses={204: None}, summary="Прочитать все свои уведомления")
    def post(self, request):
        personal_notifications(request.user).filter(read_at=None).update(read_at=timezone.now())
        return Response(status=204)


urlpatterns = [
    path("restock/<int:pk>/", subscribe_view, name="restock"),
    path("api/restock/<int:pk>/", RestockSubscriptionAPI.as_view()),
    path("api/notifications/", NotificationsAPI.as_view()),
    path("api/notifications/unread/", UnreadNotificationsAPI.as_view()),
]
