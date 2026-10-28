from django.contrib import admin, messages

from .models import Order, OrderItem, OrderStatusLog, PromoCode
from .services import OrderError, change_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "price", "quantity")

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "from_status", "to_status", "changed_by", "comment")

    def has_add_permission(self, request, obj=None):
        return False


def _status_action(status, description):
    @admin.action(description=description, permissions=["change"])
    def action(modeladmin, request, queryset):
        done = 0
        for order in queryset:
            try:
                change_status(order, status, by=request.user, comment="Через панель менеджера")
                done += 1
            except OrderError as error:
                modeladmin.message_user(request, str(error), messages.WARNING)
        if done:
            modeladmin.message_user(request, f"Обновлено заказов: {done}", messages.SUCCESS)

    action.__name__ = f"mark_{status}"
    return action


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at", "user", "full_name", "status", "delivery_method", "total")
    list_filter = ("status", "delivery_method", "created_at")
    list_select_related = ("user",)
    search_fields = ("pk", "full_name", "phone", "email", "user__username")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, OrderStatusLogInline]
    readonly_fields = (
        "user",
        "status",
        "promo_code",
        "subtotal",
        "discount",
        "delivery_cost",
        "total",
        "created_at",
        "updated_at",
    )
    actions = [
        _status_action(Order.Status.CONFIRMED, "Подтвердить"),
        _status_action(Order.Status.SHIPPED, "Передать в доставку"),
        _status_action(Order.Status.DELIVERED, "Отметить доставленными"),
        _status_action(Order.Status.CANCELLED, "Отменить (вернуть товары на склад)"),
    ]

    def has_add_permission(self, request):
        # Заказ создаётся только через сервис оформления, даже для суперпользователя.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_percent",
        "valid_from",
        "valid_until",
        "used_count",
        "max_uses",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("code",)
