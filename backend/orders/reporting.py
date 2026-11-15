import csv

from django import forms
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path

from .models import Order
from .services import sales_report as sales_report

SUMMARY_LABELS = {
    "count": "Число заказов",
    "revenue": "Выручка",
    "average": "Средний чек",
}
CSV_SECTIONS = {
    "statuses": ("По статусам", "label"),
    "deliveries": ("По способам доставки", "label"),
    "daily": ("По дням", "day"),
    "top_quantity": ("Лидеры по количеству", "name"),
    "top_revenue": ("Лидеры по стоимости позиций", "name"),
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
    report = labeled_sales_report(**form.cleaned_data) if form.is_valid() else None
    if report is not None and request.GET.get("format") == "csv":
        return sales_csv(report)
    return render(request, "orders/report.html", {"form": form, "report": report})


def labeled_sales_report(**period):
    report = sales_report(**period)
    for section, field, choices in (
        ("statuses", "status", Order.Status.choices),
        ("deliveries", "delivery_method", Order.Delivery.choices),
    ):
        labels = dict(choices)
        for row in report[section]:
            row["label"] = labels.get(row[field], row[field])
    return report


def sales_csv(report):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="sales.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Раздел", "Показатель", "Значение", "Выручка, ₽"])
    for key, value in report["summary"].items():
        writer.writerow(
            ["Итого", SUMMARY_LABELS[key], value if key == "count" else f"{value:.2f}", ""]
        )
    for section, (section_label, label_field) in CSV_SECTIONS.items():
        for row in report[section]:
            label = str(row[label_field])
            if label.lstrip().startswith(("=", "+", "-", "@")) or label.startswith(
                ("\t", "\r", "\n")
            ):
                label = "'" + label
            revenue = f"{row['revenue']:.2f}" if "revenue" in row else ""
            writer.writerow(
                [
                    section_label,
                    label,
                    row.get("count", row.get("quantity")),
                    revenue,
                ]
            )
    return response


urlpatterns = [path("reports/sales/", report_view, name="sales-report")]
