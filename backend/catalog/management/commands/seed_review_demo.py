from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from catalog.models import Product, Review
from orders.models import Order, OrderItem, OrderStatusLog

BOOK_SLUG = "war-of-worlds-1898"
DEMO_ORDER = "[Демо М1] Доставленная покупка"
DEMO_REVIEWS = (
    (5, "Напряжённая история с первых страниц."),
    (4, "Хороший повод перечитать классику."),
    (4, "История особенно интересна в контексте своего времени."),
    (5, "Мрачная атмосфера и живой рассказчик."),
    (3, "Больше всего понравилась первая половина."),
    (4, "Книга хорошо подходит для обсуждения в клубе."),
    (5, "Демо М1: рассказ держит в напряжении до самого конца."),
    (2, "Демо М1: мне было сложно втянуться в повествование."),
)


def delivered_order(buyer, book):
    order, created = Order.objects.get_or_create(
        user=buyer,
        comment=DEMO_ORDER,
        defaults={
            "status": Order.Status.DELIVERED,
            "full_name": "Демонстрационный читатель",
            "phone": "+70000000000",
            "email": buyer.email,
            "subtotal": book.price,
            "total": book.price,
        },
    )
    if created:
        OrderItem.objects.create(
            order=order,
            product=book,
            product_name=book.name,
            price=book.price,
            quantity=1,
        )
        OrderStatusLog.objects.create(
            order=order,
            to_status=Order.Status.DELIVERED,
            comment=DEMO_ORDER,
        )
    return order


class Command(BaseCommand):
    help = "Добавить доставленный демозаказ и отзывы для проверки М1 на учебной базе."

    @transaction.atomic
    def handle(self, *args, **options):
        book = (
            Product.objects.active()
            .select_for_update()
            .filter(slug=BOOK_SLUG, sku="BOOK-CLASSIC-001")
            .first()
        )
        buyer = User.objects.filter(username="buyer_demo", is_staff=False).first()
        if not book or not buyer:
            raise CommandError("Сначала загрузите книжный каталог и аккаунты командой seed_demo.")
        order = delivered_order(buyer, book)
        for index, (rating, text) in enumerate(DEMO_REVIEWS, 1):
            username = f"review_demo_{index}"
            email = f"{username}@example.test"
            author, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if created:
                author.set_unusable_password()
                author.save(update_fields=["password"])
            elif author.email != email or author.has_usable_password():
                raise CommandError(f"Имя {username} занято другим аккаунтом.")
            delivered_order(author, book)
            Review.objects.get_or_create(
                product=book,
                author=author,
                defaults={
                    "rating": rating,
                    "text": text,
                    "status": Review.Status.APPROVED if index <= 6 else Review.Status.PENDING,
                },
            )
        self.stdout.write(
            f"Демозаказ buyer_demo: /orders/{order.pk}; издание: /products/{BOOK_SLUG}"
        )
        self.stdout.write("Очередь модерации: /manager/reviews")
