from rest_framework.permissions import BasePermission


def is_manager(user) -> bool:
    return user.is_authenticated and user.has_perm("orders.change_order")


class IsShopManager(BasePermission):
    message = "Недостаточно прав для операции в кабинете сотрудника."

    def has_permission(self, request, view):
        return is_manager(request.user) and request.user.has_perms(
            view.manager_permissions.get(view.action, ())
        )
