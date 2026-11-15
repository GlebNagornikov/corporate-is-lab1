import io
import json
from pathlib import Path

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from accounts.models import User
from catalog.models import BookEdition, Category, Product
from employees.models import Department, Employee

DATA_DIR = Path(__file__).resolve().parents[2] / "demo_books"


class Command(BaseCommand):
    help = "Загрузить проверенные демонстрационные книжные издания и учётные записи."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Пароль новых демоаккаунтов")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        if len(password) < 12:
            raise CommandError("Для демо используйте пароль не короче 12 символов.")
        try:
            data = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CommandError("Не найден или повреждён манифест демоизданий.") from error
        if len(data) < 20 or len({item["sku"] for item in data}) != len(data):
            raise CommandError("Манифест должен содержать не менее 20 уникальных изданий.")
        for item in data:
            path = DATA_DIR / "covers" / item["image"]
            if path.parent != DATA_DIR / "covers" or not path.is_file():
                raise CommandError(f"Нет локальной обложки {item['image']}")
            try:
                with Image.open(path) as img:
                    img.verify()
            except (OSError, ValueError) as error:
                raise CommandError(f"Повреждённая обложка {item['image']}") from error
        call_command("setup_groups", stdout=io.StringIO())
        for name, staff in (("buyer_demo", False), ("manager_demo", True)):
            user, created = User.objects.get_or_create(
                username=name, defaults={"email": f"{name}@example.test", "is_staff": staff}
            )
            if not created and user.is_staff != staff:
                raise CommandError(f"У существующего аккаунта {name} другая роль.")
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
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
        root, _ = Category.objects.get_or_create(slug="books", defaults={"name": "Книги"})
        created_count = 0
        for item in data:
            category, _ = Category.objects.get_or_create(
                slug=item["genre_slug"], defaults={"name": item["genre"], "parent": root}
            )
            product, created = Product.objects.get_or_create(
                sku=item["sku"],
                defaults={
                    "slug": item["slug"],
                    "name": item["title"],
                    "category": category,
                    "description": item["description"],
                    "price": item["price"],
                    "stock": item["stock"],
                },
            )
            if not created:
                if product.slug != item["slug"]:
                    raise CommandError(f"Артикул {item['sku']} принадлежит другой карточке.")
                continue
            created_count += 1
            edition = BookEdition(product=product, **item["edition"])
            edition.full_clean()
            edition.save()
            image_path = DATA_DIR / "covers" / item["image"]
            product.image.save(item["image"], ContentFile(image_path.read_bytes()))
        self.stdout.write(
            f"Изданий в манифесте: {len(data)}, создано: {created_count}; "
            "пароли и изменения существующих карточек сохранены."
        )
