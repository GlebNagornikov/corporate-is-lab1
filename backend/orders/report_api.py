from django.urls import path
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, viewsets
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response

from accounts.manager_permissions import IsShopManager
from config.api_docs import MANAGER_ACCESS_ERRORS

from .reporting import labeled_sales_report, sales_csv


class ReportPeriodSerializer(serializers.Serializer):
    start = serializers.DateField(help_text="Первый день периода включительно.")
    end = serializers.DateField(help_text="Последний день периода включительно.")

    def validate(self, attrs):
        if attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("Начало периода позже окончания.")
        return attrs


class ReportSummarySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=None, decimal_places=2)
    average = serializers.DecimalField(max_digits=None, decimal_places=2)


class ReportStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class ReportDeliverySerializer(serializers.Serializer):
    delivery_method = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=None, decimal_places=2)


class ReportDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=None, decimal_places=2)


class ReportBookSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=None, decimal_places=2)


class SalesReportSerializer(serializers.Serializer):
    summary = ReportSummarySerializer()
    statuses = ReportStatusSerializer(many=True)
    deliveries = ReportDeliverySerializer(many=True)
    daily = ReportDaySerializer(many=True)
    top_quantity = ReportBookSerializer(many=True)
    top_revenue = ReportBookSerializer(many=True)


REPORT_ERRORS = {
    400: OpenApiResponse(description="Укажите обе даты в формате ГГГГ-ММ-ДД по порядку."),
    **MANAGER_ACCESS_ERRORS,
}


class SalesReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    manager_permissions = {
        "retrieve": ("orders.view_order",),
        "export": ("orders.view_order",),
    }

    def get_report(self, request):
        period = ReportPeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        return labeled_sales_report(**period.validated_data, books_only=True)

    @extend_schema(
        parameters=[ReportPeriodSerializer],
        description=(
            "Агрегаты продаж по дате оформления в часовом поясе магазина. "
            "Выручка — итоговая сумма заказов без отменённых, "
            "диаграмма статусов включает все заказы. "
            "Книги ранжируются по числу экземпляров и стоимости позиций."
        ),
        responses={200: SalesReportSerializer, **REPORT_ERRORS},
    )
    def retrieve(self, request):
        return Response(SalesReportSerializer(self.get_report(request)).data)

    @extend_schema(
        parameters=[ReportPeriodSerializer],
        description="Скачивает те же агрегаты в CSV с кодировкой UTF-8.",
        responses={(200, "text/csv"): OpenApiTypes.BINARY, **REPORT_ERRORS},
    )
    def export(self, request):
        return sales_csv(self.get_report(request))


class CSVContentNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        # The CSV is an HttpResponse. DRF only renders errors on this route.
        renderer = renderers[0]
        return renderer, renderer.media_type


urlpatterns = [
    path(
        "reports/sales/", SalesReportViewSet.as_view({"get": "retrieve"}), name="api-sales-report"
    ),
    path(
        "reports/sales/csv/",
        SalesReportViewSet.as_view(
            {"get": "export"}, content_negotiation_class=CSVContentNegotiation
        ),
        name="api-sales-report-csv",
    ),
]
