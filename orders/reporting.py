import csv

from django import forms
from django.contrib.auth.decorators import permission_required
from django.db.models import Avg, Count, DecimalField, F, Max, Sum
from django.db.models.functions import TruncDay
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path

from .models import Order, OrderItem


def sales_report(start=None, end=None):
    orders = Order.objects.all()
    if start:
        orders = orders.filter(created_at__date__gte=start)
    if end:
        orders = orders.filter(created_at__date__lte=end)
    active = orders.exclude(status=Order.Status.CANCELLED)
    items = (
        OrderItem.objects.filter(order__in=active)
        .values("product_id")
        .annotate(
            name=Max("product_name"),
            revenue=Sum(
                F("price") * F("quantity"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
            quantity=Sum("quantity"),
        )
    )
    return {
        "summary": active.aggregate(
            count=Count("pk"), revenue=Sum("total", default=0), average=Avg("total", default=0)
        ),
        "statuses": list(
            orders.order_by().values("status").annotate(count=Count("pk")).order_by("status")
        ),
        "deliveries": list(
            active.order_by()
            .values("delivery_method")
            .annotate(count=Count("pk"), revenue=Sum("total"))
            .order_by("delivery_method")
        ),
        "daily": list(
            active.annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("pk"), revenue=Sum("total"))
            .order_by("day")
        ),
        "top_quantity": list(items.order_by("-quantity", "product_id")[:10]),
        "top_revenue": list(items.order_by("-revenue", "product_id")[:10]),
    }


class PeriodForm(forms.Form):
    start = forms.DateField(
        label="С", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="По", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        values = super().clean()
        if values.get("start") and values.get("end") and values["start"] > values["end"]:
            raise forms.ValidationError("Начало периода позже окончания.")
        return values


@permission_required("orders.view_order", raise_exception=True)
def report_view(request):
    form = PeriodForm(request.GET)
    report = sales_report(**form.cleaned_data) if form.is_valid() else None
    if report is not None and request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["section", "metric", "value", "revenue"])
        for key, value in report["summary"].items():
            writer.writerow(["summary", key, value, ""])
        for section in ("statuses", "deliveries", "daily", "top_quantity", "top_revenue"):
            for row in report[section]:
                label = str(
                    row.get(
                        "name", row.get("status", row.get("delivery_method", row.get("day", "")))
                    )
                )
                if label.startswith(("=", "+", "-", "@")):
                    label = "'" + label
                writer.writerow(
                    [section, label, row.get("count", row.get("quantity")), row.get("revenue", "")]
                )
        return response
    return render(request, "orders/report.html", {"form": form, "report": report})


urlpatterns = [path("reports/sales/", report_view, name="sales-report")]
