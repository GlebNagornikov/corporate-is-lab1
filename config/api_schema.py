from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiExample


class ShopSchema(AutoSchema):
    def get_description(self):
        path = self.path
        if "payments/" in path:
            rights = "Публичный webhook с обязательной HMAC-подписью. JWT не требуется."
        elif "auth/token" in path:
            rights = "Публичная операция. Получение токена: до 10 запросов в минуту с IP."
        elif "auth/register" in path:
            rights = "Публичная регистрация покупателя."
        elif "auth/me" in path:
            rights = "Профиль текущего пользователя. Требуется JWT или сессия."
        elif "catalog/" in path:
            rights = "Чтение публично; отзыв требует входа. Один отзыв на товар."
        elif "employees" in path or "departments" in path:
            rights = "Нужны Django-права view/add/change/delete соответствующей модели."
        elif "orders" in path:
            rights = "Свои заказы; view_order — все, change_order — смена статуса."
        else:
            rights = "JWT или сессия. Операция выполняется только над данными текущего покупателя."
        return (
            (super().get_description() or "")
            + "\n\n"
            + rights
            + "\nЛимиты: 60/600 в минуту (аноним/пользователь). Сессия требует CSRF."
        )

    def get_examples(self):
        examples = super().get_examples()
        if examples:
            return examples
        path = self.path
        if "payments/" in path:
            value = {"payment_id": "550e8400-e29b-41d4-a716-446655440000", "outcome": "success"}
        elif "auth/token/refresh" in path:
            value = {"refresh": "<refresh-token>"}
        elif "auth/token" in path:
            value = {"username": "buyer", "password": "<your-password>"}
        elif "auth/register" in path:
            value = {
                "username": "buyer",
                "email": "buyer@example.test",
                "password": "<your-password>",
            }
        elif "auth/me" in path:
            value = {
                "username": "buyer",
                "email": "buyer@example.test",
                "first_name": "",
                "last_name": "",
                "is_manager": False,
            }
        elif "reviews" in path:
            value = {"rating": 5, "text": "Хороший товар"}
        elif "status" in path:
            value = {"status": "confirmed", "comment": "Оплата проверена"}
        elif "orders" in path:
            value = {
                "full_name": "Иван Иванов",
                "phone": "8 (913) 555-12-34",
                "email": "buyer@example.test",
                "delivery_method": "pickup",
            }
        elif "cart/merge" in path:
            value = {"items": [{"product": 1, "quantity": 1}]}
        elif "cart" in path:
            value = {"product": 1, "variant": 1, "quantity": 1}
        elif "wishlist" in path:
            value = {"product": 1}
        elif "departments" in path:
            value = {"name": "Продажи", "description": "Отдел продаж"}
        else:
            value = {
                "full_name": "Иван Иванов",
                "position": "Менеджер",
                "hired_at": "2026-11-04",
                "department": 1,
            }
        response = {"id": 1, **value}
        if "auth/token" in path:
            response = {"access": "<access-token>", "refresh": "<refresh-token>"}
        elif "auth/register" in path:
            response.pop("password")
        elif "payments/" in path:
            response = {"status": "success"}
        elif "cart" in path:
            response = {"items": [], "count": 0, "total": "0.00"}
        return [
            OpenApiExample(
                "Пример ответа", value=response, response_only=True, status_codes=["200", "201"]
            ),
            OpenApiExample("Пример входных данных", value=value, request_only=True),
            OpenApiExample(
                "Ошибка прав",
                value={"detail": "У вас недостаточно прав для выполнения данного действия."},
                response_only=True,
                status_codes=["403"],
            ),
        ]
