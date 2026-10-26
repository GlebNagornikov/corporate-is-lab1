import django_filters

from .models import Category, Product


class ProductFilter(django_filters.FilterSet):
    """Фильтры каталога. Один класс работает и для HTML-витрины, и для REST API."""

    q = django_filters.CharFilter(method="filter_search", label="Поиск")
    category = django_filters.CharFilter(method="filter_category", label="Категория")
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte", label="Цена от")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte", label="Цена до")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock", label="В наличии")
    on_sale = django_filters.BooleanFilter(method="filter_on_sale", label="Со скидкой")
    ordering = django_filters.OrderingFilter(
        fields=(
            ("price", "price"),
            ("created_at", "created_at"),
            ("rating", "rating"),
            ("name", "name"),
        ),
        field_labels={
            "price": "Цена",
            "created_at": "Новизна",
            "rating": "Рейтинг",
            "name": "Название",
        },
        label="Сортировка",
    )

    class Meta:
        model = Product
        fields = []

    def filter_search(self, queryset, name, value):
        return queryset.search(value) if value.strip() else queryset

    def filter_category(self, queryset, name, value):
        category = Category.objects.filter(slug=value).first()
        if category is None:
            return queryset.none()
        return queryset.filter(category_id__in=category.get_descendant_ids())

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset

    def filter_on_sale(self, queryset, name, value):
        return queryset.filter(old_price__isnull=False) if value else queryset
