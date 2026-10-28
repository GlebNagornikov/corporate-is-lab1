from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUPS = {
    "Менеджеры магазина": [
        "orders.view_order",
        "orders.change_order",
        "orders.view_orderitem",
        "orders.view_orderstatuslog",
        "orders.view_promocode",
        "orders.add_promocode",
        "orders.change_promocode",
        "catalog.view_category",
        "catalog.view_product",
        "catalog.change_product",
        "catalog.view_review",
        "catalog.change_review",
    ],
}


class Command(BaseCommand):
    help = "Создаёт группы пользователей и выдаёт им права (можно запускать повторно)"

    def handle(self, *args, **options):
        for name, codes in GROUPS.items():
            group, _ = Group.objects.get_or_create(name=name)
            permissions = []
            for code in codes:
                app_label, codename = code.split(".")
                permissions.append(
                    Permission.objects.get(content_type__app_label=app_label, codename=codename)
                )
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"{name}: прав {len(permissions)}"))
