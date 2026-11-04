import csv

from django import forms
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path

from .services import sales_report as sales_report


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
