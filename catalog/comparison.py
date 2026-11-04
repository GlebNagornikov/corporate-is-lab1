from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_POST

from .models import Category, Product

KEY = "comparison"


def root_category(category_id):
    parents = dict(Category.objects.values_list("pk", "parent_id"))
    seen = set()
    while parents.get(category_id):
        if category_id in seen:
            raise ValidationError("Цикл категорий.")
        seen.add(category_id)
        category_id = parents[category_id]
    return category_id


def comparison_products(session):
    return list(
        Product.objects.active().with_rating().filter(pk__in=session.get(KEY, [])).order_by("pk")
    )


def add_comparison(session, product):
    products = comparison_products(session)
    if product.pk in [p.pk for p in products]:
        return
    if len(products) >= 4:
        raise ValidationError("Можно сравнить не больше четырёх товаров.")
    if products and root_category(products[0].category_id) != root_category(product.category_id):
        raise ValidationError("Выберите товары одной категории верхнего уровня.")
    session[KEY] = [p.pk for p in products] + [product.pk]


def comparison_rows(products):
    rows = []
    for label, field in [
        ("Цена от, ₽", "price"),
        ("Скидка, %", "discount_percent"),
        ("Рейтинг", "rating"),
        ("В наличии", "in_stock"),
    ]:
        values = [
            str(getattr(p, field) if getattr(p, field) is not None else "—") for p in products
        ]
        rows.append((label, values, len(set(values)) > 1))
    keys = sorted({key for p in products for key in p.attributes})
    for key in keys:
        values = [str(p.attributes.get(key, "—")) for p in products]
        rows.append((key, values, len(set(values)) > 1))
    return rows


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
