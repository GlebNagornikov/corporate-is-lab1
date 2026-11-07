from django.db.models import Sum
from rest_framework.pagination import PageNumberPagination

from .filters import ProductFilter
from .models import Product


class ProductPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["total"] = None
        if self.request.query_params.get("category", "").strip():
            products = self.page.paginator.object_list
            total = products.aggregate(total=Sum("price", default=0))["total"]
            response.data["total"] = format(total, ".2f")
        response.data["suggestion"] = None
        query = self.request.query_params.get("q", "").strip()
        if query and response.data["count"] == 0:
            filters = self.request.query_params.copy()
            filters.pop("q", None)
            candidates = ProductFilter(filters, queryset=Product.objects.active().with_rating()).qs
            response.data["suggestion"] = (
                candidates.similar_to(query)
                .order_by("-similarity", "pk")
                .values_list("name", flat=True)
                .first()
            )
        return response

    def get_paginated_response_schema(self, schema):
        result = super().get_paginated_response_schema(schema)
        result["properties"]["total"] = {
            "type": "string",
            "format": "decimal",
            "nullable": True,
            "example": "1290.00",
            "description": "Сумма цен всех найденных товаров при фильтрации по категории.",
        }
        result["properties"]["suggestion"] = {
            "type": "string",
            "nullable": True,
            "example": None,
            "description": "Вариант поискового запроса, если по исходному запросу нет товаров.",
        }
        result["required"].extend(["total", "suggestion"])
        return result
