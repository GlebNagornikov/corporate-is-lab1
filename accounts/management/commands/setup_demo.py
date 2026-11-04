import io
from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from accounts.models import User
from catalog.models import Category, Product, ProductVariant
from employees.models import Department, Employee
from orders.models import PromoCode


class Command(BaseCommand):
    help = "Создать buyer_demo/manager_demo и демонстрационные товары"

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)
        parser.add_argument("--reset-password", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if len(options["password"]) < 12:
            raise CommandError("Для демо используйте пароль не короче 12 символов.")
        call_command("setup_groups", stdout=io.StringIO())
        for username, staff in [("buyer_demo", False), ("manager_demo", True)]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.test",
                    "is_staff": staff,
                    "phone": "+79135551234",
                },
            )
            if not created and user.is_staff != staff:
                raise CommandError(
                    f"Существующий аккаунт {username} имеет другую роль; он не изменён."
                )
            if created or options["reset_password"]:
                user.set_password(options["password"])
                user.save()
            if staff:
                user.groups.add(Group.objects.get(name="Менеджеры магазина"))
                if not user.employee_id:
                    department, _ = Department.objects.get_or_create(name="Продажи")
                    user.employee = Employee.objects.create(
                        full_name="Демонстрационный менеджер",
                        position="Менеджер магазина",
                        hired_at=timezone.localdate(),
                        department=department,
                    )
                    user.save(update_fields=["employee"])
        category, _ = Category.objects.get_or_create(
            slug="demo", defaults={"name": "Демонстрационные товары"}
        )
        for index in range(1, 6):
            product, created = Product.objects.get_or_create(
                sku=f"DEMO-{index}",
                defaults={
                    "category": category,
                    "name": f"Демо-футболка {index}",
                    "slug": f"demo-shirt-{index}",
                    "price": 1000 + index * 100,
                    "stock": 10 if index < 5 else 0,
                    "attributes": {"Материал": "Хлопок" if index % 2 else "Лён", "Модель": index},
                },
            )
            if created:
                image = io.BytesIO()
                Image.new("RGB", (320, 240), (40 * index, 100, 150)).save(image, format="PNG")
                product.image.save(f"demo-{index}.png", ContentFile(image.getvalue()))
                for size in ("S", "L"):
                    ProductVariant.objects.create(
                        product=product,
                        name=f"{size}, синий",
                        sku=f"DEMO-{index}-{size}",
                        price=product.price,
                        stock=5 if index < 5 else 0,
                    )
        now = timezone.now()
        for code in ("STUDENT10", "CHECKPOINT10"):
            PromoCode.objects.get_or_create(
                code=code,
                defaults={
                    "discount_percent": 10,
                    "valid_from": now - timedelta(days=1),
                    "valid_until": now + timedelta(days=365),
                },
            )
        self.stdout.write(
            "Готово: buyer_demo, manager_demo; DEMO-1…5 и CHECKPOINT10. Пароли не сброшены."
        )
