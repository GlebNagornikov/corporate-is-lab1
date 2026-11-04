from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_POST

from .models import Product
from .services import add_comparison as add_comparison
from .services import comparison_products as comparison_products
from .services import comparison_rows as comparison_rows
from .services import root_category as root_category

KEY = "comparison"


def compare(request):
    products = comparison_products(request.session)
    return render(
        request,
        "catalog/comparison.html",
        {"products": products, "rows": comparison_rows(products)},
    )


@require_POST
def compare_change(request, pk):
    if request.POST.get("action") == "remove":
        request.session[KEY] = [i for i in request.session.get(KEY, []) if i != pk]
    else:
        try:
            add_comparison(request.session, get_object_or_404(Product.objects.active(), pk=pk))
        except ValidationError as error:
            messages.error(request, error.messages[0])
    return redirect("comparison")


urlpatterns = [
    path("compare/", compare, name="comparison"),
    path("compare/<int:pk>/", compare_change, name="compare-change"),
]
