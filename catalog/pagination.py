from django.db.models import Sum
from rest_framework.pagination import PageNumberPagination


class ProductPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["total"] = None
        if self.request.query_params.get("category", "").strip():
            products = self.page.paginator.object_list
            total = products.aggregate(total=Sum("price", default=0))["total"]
            response.data["total"] = format(total, ".2f")
        return response

    def get_paginated_response_schema(self, schema):
        result = super().get_paginated_response_schema(schema)
        result["properties"]["total"] = {
            "type": "string",
            "format": "decimal",
            "nullable": True,
            "description": "Сумма цен всех найденных товаров при фильтрации по категории.",
        }
        result["required"].append("total")
        return result
